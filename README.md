# AI Business Assistant

The AI Business Assistant is the overall product. **Mini CRM** is one module of
the larger project. This Week 3 local prototype provides the foundation for one
small-business owner to manage clients and tasks.

## Week 3 features

- Dashboard totals for clients, in-progress tasks, overdue tasks, and completed tasks.
- Client create, view, edit, delete, and search by name, email, or company.
- Task create, view, edit, delete, status changes, and filters for status, due date,
  and client.
- Local SQLite storage that persists across restarts.
- Fictional demo clients and tasks inserted only on the database's first initialization.

This is an unauthenticated local learning project. Do not deploy it publicly or
enter real customer information. AI, calendar, reminders, automation, and advanced
analytics are not implemented in this Week 3 version.

## Requirements

- Python 3.9 or newer
- Windows PowerShell

## Start the application (Windows PowerShell)

Open PowerShell in the project folder and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

If PowerShell prevents environment activation, allow it for the current terminal
only, then activate the environment:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Open <http://127.0.0.1:5000/> in your browser. The SQLite database is created
automatically at `data\app.db` and is intentionally ignored by Git. Stop the
development server with `Ctrl+C`.

## Run tests

With the virtual environment activated:

```powershell
python -m unittest -v
```

The tests use separate temporary databases and do not alter existing records in
`data\app.db`.
