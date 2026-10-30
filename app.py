import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)


TASK_STATUSES = ("To Do", "In Progress", "Done")
# Common email syntax: an unquoted dot-separated local part and DNS labels.
EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
    r"(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "local-development-key"),
        DATABASE=os.environ.get(
            "DATABASE_PATH", str(Path(app.root_path) / "data" / "app.db")
        ),
    )
    if test_config:
        app.config.update(test_config)

    initialize_database(app)

    @app.teardown_appcontext
    def close_database(_error=None):
        connection = g.pop("database", None)
        if connection is not None:
            connection.close()

    @app.route("/")
    def dashboard():
        today = date.today().isoformat()
        metrics = get_db().execute(
            """
            SELECT
                (SELECT COUNT(*) FROM clients) AS total_clients,
                (SELECT COUNT(*) FROM tasks) AS total_tasks,
                (SELECT COUNT(*) FROM tasks WHERE status = 'In Progress')
                    AS in_progress_tasks,
                (SELECT COUNT(*) FROM tasks
                    WHERE due_date < ? AND status != 'Done') AS overdue_tasks,
                (SELECT COUNT(*) FROM tasks WHERE status = 'Done')
                    AS completed_tasks
            """,
            (today,),
        ).fetchone()
        return render_template("dashboard.html", metrics=metrics)

    @app.route("/clients")
    def clients():
        search = request.args.get("q", "").strip()
        if search:
            pattern = f"%{search}%"
            client_rows = get_db().execute(
                """
                SELECT * FROM clients
                WHERE name LIKE ? COLLATE NOCASE
                   OR email LIKE ? COLLATE NOCASE
                   OR company LIKE ? COLLATE NOCASE
                ORDER BY name COLLATE NOCASE
                """,
                (pattern, pattern, pattern),
            ).fetchall()
        else:
            client_rows = get_db().execute(
                "SELECT * FROM clients ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return render_template(
            "clients.html", clients=client_rows, search=search
        )

    @app.route("/clients/new", methods=("GET", "POST"))
    def new_client():
        if request.method == "POST":
            client = client_form_data()
            error = validate_client(client)
            if error:
                flash(error, "error")
                return render_template(
                    "client_form.html", client=client, is_edit=False
                )

            get_db().execute(
                """
                INSERT INTO clients (name, phone, email, company, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                tuple(client[field] or None for field in (
                    "name", "phone", "email", "company", "notes"
                )),
            )
            get_db().commit()
            flash("Client created.", "success")
            return redirect(url_for("clients"))

        return render_template(
            "client_form.html", client=empty_client(), is_edit=False
        )

    @app.route("/clients/<int:client_id>/edit", methods=("GET", "POST"))
    def edit_client(client_id):
        client_row = get_client_or_404(client_id)
        if request.method == "POST":
            client = client_form_data()
            error = validate_client(client)
            if error:
                flash(error, "error")
                return render_template(
                    "client_form.html",
                    client=client,
                    is_edit=True,
                )

            get_db().execute(
                """
                UPDATE clients
                SET name = ?, phone = ?, email = ?, company = ?, notes = ?
                WHERE id = ?
                """,
                tuple(client[field] or None for field in (
                    "name", "phone", "email", "company", "notes"
                )) + (client_id,),
            )
            get_db().commit()
            flash("Client updated.", "success")
            return redirect(url_for("clients"))

        return render_template(
            "client_form.html", client=client_row, is_edit=True
        )

    @app.route("/clients/<int:client_id>/delete", methods=("POST",))
    def delete_client(client_id):
        get_client_or_404(client_id)
        get_db().execute("DELETE FROM clients WHERE id = ?", (client_id,))
        get_db().commit()
        flash("Client deleted. Their tasks were kept without a linked client.", "success")
        return redirect(url_for("clients"))

    @app.route("/tasks")
    def tasks():
        status_filter = request.args.get("status", "").strip()
        due_date_filter = request.args.get("due_date", "").strip()
        client_filter = request.args.get("client_id", "").strip()
        filters = []
        parameters = []

        if status_filter:
            if status_filter not in TASK_STATUSES:
                flash("Choose a valid task status filter.", "error")
                status_filter = ""
            else:
                filters.append("tasks.status = ?")
                parameters.append(status_filter)

        if due_date_filter:
            if not valid_date(due_date_filter):
                flash("Enter a valid due date filter.", "error")
                due_date_filter = ""
            else:
                filters.append("tasks.due_date = ?")
                parameters.append(due_date_filter)

        if client_filter:
            if client_filter == "none":
                filters.append("tasks.client_id IS NULL")
            else:
                try:
                    client_id = int(client_filter)
                except ValueError:
                    flash("Choose a valid client filter.", "error")
                    client_filter = ""
                else:
                    filters.append("tasks.client_id = ?")
                    parameters.append(client_id)

        query = """
            SELECT tasks.*, clients.name AS client_name
            FROM tasks
            LEFT JOIN clients ON clients.id = tasks.client_id
        """
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY tasks.due_date, tasks.id DESC"

        task_rows = get_db().execute(query, parameters).fetchall()
        client_rows = get_db().execute(
            "SELECT id, name FROM clients ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return render_template(
            "tasks.html",
            tasks=task_rows,
            clients=client_rows,
            statuses=TASK_STATUSES,
            status_filter=status_filter,
            due_date_filter=due_date_filter,
            client_filter=client_filter,
            today=date.today().isoformat(),
        )

    @app.route("/tasks/new", methods=("GET", "POST"))
    def new_task():
        if request.method == "POST":
            task = task_form_data()
            error = validate_task(task)
            if error:
                flash(error, "error")
                return render_template(
                    "task_form.html",
                    task=task,
                    clients=list_clients(),
                    statuses=TASK_STATUSES,
                    is_edit=False,
                )

            get_db().execute(
                """
                INSERT INTO tasks (title, description, due_date, status, client_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    task["title"],
                    task["description"] or None,
                    task["due_date"],
                    task["status"],
                    task["client_id"],
                ),
            )
            get_db().commit()
            flash("Task created.", "success")
            return redirect(url_for("tasks"))

        return render_template(
            "task_form.html",
            task=empty_task(),
            clients=list_clients(),
            statuses=TASK_STATUSES,
            is_edit=False,
        )

    @app.route("/tasks/<int:task_id>/edit", methods=("GET", "POST"))
    def edit_task(task_id):
        task_row = get_task_or_404(task_id)
        if request.method == "POST":
            task = task_form_data()
            error = validate_task(task)
            if error:
                flash(error, "error")
                return render_template(
                    "task_form.html",
                    task=task,
                    clients=list_clients(),
                    statuses=TASK_STATUSES,
                    is_edit=True,
                )

            get_db().execute(
                """
                UPDATE tasks
                SET title = ?, description = ?, due_date = ?, status = ?,
                    client_id = ?
                WHERE id = ?
                """,
                (
                    task["title"],
                    task["description"] or None,
                    task["due_date"],
                    task["status"],
                    task["client_id"],
                    task_id,
                ),
            )
            get_db().commit()
            flash("Task updated.", "success")
            return redirect(url_for("tasks"))

        return render_template(
            "task_form.html",
            task=task_row,
            clients=list_clients(),
            statuses=TASK_STATUSES,
            is_edit=True,
        )

    @app.route("/tasks/<int:task_id>/delete", methods=("POST",))
    def delete_task(task_id):
        get_task_or_404(task_id)
        get_db().execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        get_db().commit()
        flash("Task deleted.", "success")
        return redirect(url_for("tasks"))

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    return app


def get_db():
    if "database" not in g:
        connection = sqlite3.connect(current_app_database())
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.database = connection
    return g.database


def current_app_database():
    from flask import current_app

    return current_app.config["DATABASE"]


def initialize_database(app):
    database_path = Path(app.config["DATABASE"])
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            company TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'To Do'
                CHECK (status IN ('To Do', 'In Progress', 'Done')),
            client_id INTEGER,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS app_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    seeded = connection.execute(
        "SELECT value FROM app_metadata WHERE key = 'demo_data_seeded'"
    ).fetchone()
    if seeded is None:
        seed_demo_data(connection)
        connection.execute(
            "INSERT INTO app_metadata (key, value) VALUES ('demo_data_seeded', 'yes')"
        )
    connection.commit()
    connection.close()


def seed_demo_data(connection):
    client_ids = []
    clients = (
        ("Amelia Byrne", "087 555 0142", "amelia@example.test", "Byrne Floral Studio",
         "Fictional demo client."),
        ("Noah Kelly", "087 555 0187", "noah@example.test", "Kelly Home Repairs",
         "Fictional demo client."),
        ("Sofia Murphy", None, "sofia@example.test", "Murphy Design Co.",
         "Fictional demo client."),
    )
    for client in clients:
        cursor = connection.execute(
            """
            INSERT INTO clients (name, phone, email, company, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            client,
        )
        client_ids.append(cursor.lastrowid)

    today = date.today()
    tasks = (
        (
            "Prepare flower order",
            "Confirm the seasonal arrangement and delivery details.",
            (today - timedelta(days=3)).isoformat(),
            "To Do",
            client_ids[0],
        ),
        (
            "Send project estimate",
            "Follow up with a written estimate for the repair work.",
            (today + timedelta(days=2)).isoformat(),
            "In Progress",
            client_ids[1],
        ),
        (
            "Review brand concepts",
            "Discuss the completed first-round design concepts.",
            (today + timedelta(days=7)).isoformat(),
            "Done",
            client_ids[2],
        ),
        (
            "Update supplier list",
            "Check current prices and contact details for suppliers.",
            (today + timedelta(days=10)).isoformat(),
            "To Do",
            None,
        ),
    )
    connection.executemany(
        """
        INSERT INTO tasks (title, description, due_date, status, client_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        tasks,
    )


def empty_client():
    return {"name": "", "phone": "", "email": "", "company": "", "notes": ""}


def client_form_data():
    return {
        field: request.form.get(field, "").strip()
        for field in ("name", "phone", "email", "company", "notes")
    }


def validate_client(client):
    if not client["name"]:
        return "Client name is required."
    if len(client["name"]) > 120:
        return "Client name must be 120 characters or fewer."
    if not client["phone"] and not client["email"]:
        return "Provide at least a phone number or an email address."
    if len(client["phone"]) > 40:
        return "Phone number must be 40 characters or fewer."
    if len(client["email"]) > 254:
        return "Email address must be 254 characters or fewer."
    if client["email"]:
        local_part = client["email"].split("@", 1)[0]
        if len(local_part) > 64 or not EMAIL_PATTERN.fullmatch(client["email"]):
            return "Enter a valid email address."
    if len(client["company"]) > 120:
        return "Company must be 120 characters or fewer."
    if len(client["notes"]) > 2000:
        return "Notes must be 2,000 characters or fewer."
    return None


def empty_task():
    return {
        "title": "",
        "description": "",
        "due_date": "",
        "status": "To Do",
        "client_id": "",
    }


def task_form_data():
    client_id = request.form.get("client_id", "").strip()
    if client_id:
        try:
            client_id = int(client_id)
        except ValueError:
            client_id = -1
    else:
        client_id = None
    return {
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "due_date": request.form.get("due_date", "").strip(),
        "status": request.form.get("status", "").strip(),
        "client_id": client_id,
    }


def validate_task(task):
    if not task["title"]:
        return "Task title is required."
    if len(task["title"]) > 160:
        return "Task title must be 160 characters or fewer."
    if len(task["description"]) > 2000:
        return "Description must be 2,000 characters or fewer."
    if not valid_date(task["due_date"]):
        return "Enter a valid due date."
    if task["status"] not in TASK_STATUSES:
        return "Choose a valid task status."
    if task["client_id"] is not None:
        client = get_db().execute(
            "SELECT id FROM clients WHERE id = ?", (task["client_id"],)
        ).fetchone()
        if client is None:
            return "Choose an existing client or leave the client field blank."
    return None


def valid_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat() == value
    except (TypeError, ValueError):
        return False


def list_clients():
    return get_db().execute(
        "SELECT id, name FROM clients ORDER BY name COLLATE NOCASE"
    ).fetchall()


def get_client_or_404(client_id):
    client = get_db().execute(
        "SELECT * FROM clients WHERE id = ?", (client_id,)
    ).fetchone()
    if client is None:
        abort(404)
    return client


def get_task_or_404(task_id):
    task = get_db().execute(
        "SELECT * FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if task is None:
        abort(404)
    return task


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)
