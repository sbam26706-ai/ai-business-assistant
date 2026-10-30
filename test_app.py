import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import create_app, get_db


class DatabaseIsolationTests(unittest.TestCase):
    def test_imports_and_suite_never_open_normal_database(self):
        # A fresh interpreter exercises imports as well as application setup.
        script = r'''
import os
import pathlib
import sqlite3
import unittest
from unittest.mock import patch

normal_paths = {
    pathlib.Path(os.environ["DATABASE_PATH"]).resolve(),
    (pathlib.Path.cwd() / "data" / "app.db").resolve(),
}
original_connect = sqlite3.connect

def isolated_connect(database, *args, **kwargs):
    if pathlib.Path(database).resolve() in normal_paths:
        raise AssertionError("Tests attempted to open a normal database")
    return original_connect(database, *args, **kwargs)

with patch("sqlite3.connect", side_effect=isolated_connect):
    import app
    import test_app
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        test_app.BusinessAssistantTests
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
'''
        with tempfile.TemporaryDirectory() as directory:
            normal_database = Path(directory) / "normal.db"
            for existing in (False, True):
                with self.subTest(existing_database=existing):
                    if existing:
                        normal_database.write_bytes(b"Existing database must stay untouched")
                    before = normal_database.read_bytes() if existing else None
                    environment = os.environ.copy()
                    environment["DATABASE_PATH"] = str(normal_database)
                    environment["PYTHONDONTWRITEBYTECODE"] = "1"
                    result = subprocess.run(
                        [sys.executable, "-B", "-c", script],
                        cwd=Path(__file__).resolve().parent,
                        env=environment,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    if existing:
                        self.assertEqual(normal_database.read_bytes(), before)
                    else:
                        self.assertFalse(normal_database.exists())


class BusinessAssistantTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        database = Path(self.temporary_directory.name) / "test.db"
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-key",
                "DATABASE": str(database),
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            get_db().execute("DELETE FROM tasks")
            get_db().execute("DELETE FROM clients")
            get_db().commit()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def create_client(self, name="Test Client", phone="555-0100", email=""):
        response = self.client.post(
            "/clients/new",
            data={
                "name": name,
                "phone": phone,
                "email": email,
                "company": "Test Company",
                "notes": "",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            return get_db().execute(
                "SELECT * FROM clients WHERE name = ?", (name,)
            ).fetchone()

    def create_task(
        self,
        title,
        due_date,
        status="To Do",
        client_id="",
    ):
        return self.client.post(
            "/tasks/new",
            data={
                "title": title,
                "description": "",
                "due_date": due_date,
                "status": status,
                "client_id": str(client_id),
            },
            follow_redirects=True,
        )

    def test_demo_data_is_seeded_once_and_has_required_examples(self):
        database = Path(self.temporary_directory.name) / "seeded.db"
        seeded_app = create_app(
            {"TESTING": True, "DATABASE": str(database)}
        )
        with seeded_app.app_context():
            counts = get_db().execute(
                "SELECT (SELECT COUNT(*) FROM clients), (SELECT COUNT(*) FROM tasks)"
            ).fetchone()
            self.assertEqual(tuple(counts), (3, 4))
            self.assertEqual(
                get_db().execute(
                    "SELECT COUNT(*) FROM tasks WHERE client_id IS NULL"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                get_db().execute(
                    "SELECT COUNT(*) FROM tasks WHERE due_date < ? AND status != 'Done'",
                    (date.today().isoformat(),),
                ).fetchone()[0],
                1,
            )
        create_app({"TESTING": True, "DATABASE": str(database)})
        with seeded_app.app_context():
            self.assertEqual(
                get_db().execute("SELECT COUNT(*) FROM clients").fetchone()[0], 3
            )

    def test_client_validation_search_and_task_preserving_delete(self):
        invalid = self.client.post(
            "/clients/new",
            data={"name": "No contact", "phone": "", "email": ""},
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn(b"at least a phone number or an email", invalid.data)

        client = self.create_client(name="Casey Example", phone="", email="casey@example.test")
        self.create_task(
            "Follow up",
            (date.today() + timedelta(days=1)).isoformat(),
            client_id=client["id"],
        )
        response = self.client.get("/clients?q=CASEY")
        self.assertIn(b"Casey Example", response.data)

        response = self.client.post(
            f"/clients/{client['id']}/edit",
            data={
                "name": "Casey Updated",
                "phone": "555-0123",
                "email": "",
                "company": "Updated Company",
                "notes": "",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Casey Updated", response.data)

        response = self.client.post(
            f"/clients/{client['id']}/delete", follow_redirects=True
        )
        self.assertIn(b"tasks were kept", response.data)
        with self.app.app_context():
            task = get_db().execute(
                "SELECT client_id FROM tasks WHERE title = 'Follow up'"
            ).fetchone()
            self.assertIsNone(task["client_id"])

    def test_task_validation_filters_and_crud(self):
        invalid = self.client.post(
            "/tasks/new",
            data={"title": "", "due_date": "", "status": "To Do", "client_id": ""},
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn(b"Task title is required", invalid.data)

        client = self.create_client()
        due_date = (date.today() + timedelta(days=4)).isoformat()
        self.create_task("Filtered task", due_date, "In Progress", client["id"])
        self.create_task("Other task", due_date, "Done")

        response = self.client.get(
            f"/tasks?status=In+Progress&due_date={due_date}&client_id={client['id']}"
        )
        self.assertIn(b"Filtered task", response.data)
        self.assertNotIn(b"Other task", response.data)

        with self.app.app_context():
            task = get_db().execute(
                "SELECT id FROM tasks WHERE title = 'Filtered task'"
            ).fetchone()
        updated = self.client.post(
            f"/tasks/{task['id']}/edit",
            data={
                "title": "Updated task",
                "description": "",
                "due_date": due_date,
                "status": "Done",
                "client_id": "",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Updated task", updated.data)
        deleted = self.client.post(
            f"/tasks/{task['id']}/delete", follow_redirects=True
        )
        self.assertIn(b"Task deleted.", deleted.data)

    def test_dashboard_metrics_use_current_data(self):
        empty_dashboard = self.client.get("/")
        self.assertIn(b"There are no records yet", empty_dashboard.data)

        client = self.create_client()
        self.create_task(
            "Overdue open",
            (date.today() - timedelta(days=1)).isoformat(),
            "To Do",
            client["id"],
        )
        self.create_task(
            "Active",
            (date.today() + timedelta(days=1)).isoformat(),
            "In Progress",
            client["id"],
        )
        self.create_task(
            "Finished overdue",
            (date.today() - timedelta(days=2)).isoformat(),
            "Done",
        )

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        dashboard_html = response.data.decode()
        self.assertRegex(
            dashboard_html,
            r"Total clients</span>\s*<strong class=\"metric-value\">1</strong>",
        )
        self.assertRegex(
            dashboard_html,
            r"In progress</span>\s*<strong class=\"metric-value\">1</strong>",
        )
        self.assertRegex(
            dashboard_html,
            r"Overdue tasks</span>\s*<strong class=\"metric-value\">1</strong>",
        )
        self.assertRegex(
            dashboard_html,
            r"Completed</span>\s*<strong class=\"metric-value\">1</strong>",
        )
        with self.app.app_context():
            self.assertEqual(
                get_db().execute(
                    "SELECT COUNT(*) FROM tasks WHERE due_date < ? AND status != 'Done'",
                    (date.today().isoformat(),),
                ).fetchone()[0],
                1,
            )


if __name__ == "__main__":
    unittest.main()
