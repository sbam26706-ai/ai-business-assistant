# AI Business Assistant — Application Specification

**Project identity:** AI Business Assistant is the overarching product. **Mini CRM** is one module within it, not the name or full scope of the product.

**Specification status:** Agreed product vision and scoped Week 3 implementation, based on 25 planning decisions.

## 1. Project Overview

Build an extensible **AI Business Assistant** for owners of different kinds of small businesses, with the longer-term ability to configure modules and workflows for particular industries. The full product will combine a Mini CRM, task management, calendar and scheduling, business analytics, and an AI assistant.

**Week 3 implements the foundation, not the entire product:** a local web application for one small-business owner to manage clients and tasks. It is a learning project that must be generated from this specification, run locally, and be committed to Git before subsequent improvements.

**Week 3 goal:** A functional CRM and task-management foundation with persistent SQLite storage, client and task CRUD, search and filtering, and a summary dashboard.

**Not part of the Week 3 acceptance criteria:** live AI functionality, calendar, automatic reminders, bulk editing, animations, theme customization, interactive charts, sales/income tracking, and voice input. These are agreed future product capabilities, not requirements for the initial scaffold.

**Scope principle:** Keep the Week 3 foundation functional and beginner-friendly, while naming modules and organizing code so later capabilities can be added without rebuilding the app from scratch.

## 2. Intended User and Access

- The Week 3 prototype is used by one small-business owner. The future product is intended for different kinds of small businesses, not just one trade or service category.
- No registration, login, roles, or employee accounts in the Week 3 local prototype.
- Run on the user's own computer, accessed through a browser at `http://127.0.0.1:5000/` (or the port shown by Flask).
- Do not deploy publicly or enter real customer information in this unauthenticated prototype.

## 3. Technology and Project Structure

- Backend: Python 3 and Flask.
- Persistence: SQLite database stored locally.
- Frontend: server-rendered HTML templates, CSS, and minimal JavaScript where useful.
- Use Python's built-in `sqlite3` module or a simple, documented equivalent. Prefer a small number of understandable dependencies.
- Keep database queries parameterized; never interpolate user input into SQL strings.
- Suggested structure (the agent may adjust with a clear explanation):

```text
ai-business-assistant/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── docs/
│   └── specification.md
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── clients.html
│   ├── client_form.html
│   ├── tasks.html
│   └── task_form.html
├── static/
│   └── style.css
└── data/
    └── app.db          # created at runtime; ignored by Git
```

- Keep code readable for a beginner. Add simple error handling and clear setup instructions.
- Do not commit the SQLite database, virtual environment, credentials, or temporary files.

## 4. Data Model

### 4.1 Client

| Field | Type | Rules |
|---|---|---|
| id | Integer | Primary key, auto-generated |
| name | Text | Required, non-empty |
| phone | Text | Optional individually |
| email | Text | Optional individually; validate format if provided |
| company | Text | Optional |
| notes | Text | Optional |

**Validation:** A client must have a name and at least one contact method: phone **or** email. Trim whitespace. Display clear validation messages rather than saving invalid records.

### 4.2 Task

| Field | Type | Rules |
|---|---|---|
| id | Integer | Primary key, auto-generated |
| title | Text | Required, non-empty |
| description | Text | Optional |
| due_date | Date | Required; use `YYYY-MM-DD` in storage |
| status | Text | One of `To Do`, `In Progress`, `Done`; default `To Do` |
| client_id | Integer / NULL | Optional foreign key to Client |

- Tasks may exist without an associated client.
- If a client is deleted, preserve their tasks and set their `client_id` to `NULL` (`ON DELETE SET NULL` or equivalent application logic).
- Enable SQLite foreign-key enforcement on each connection if using SQLite foreign keys.
- A task is **overdue** when its due date is before the current local date and its status is not `Done`.

## 5. Required Features — Week 3

### 5.1 Dashboard

Show four summary metrics:
1. Total number of clients.
2. Number of tasks with status `In Progress`.
3. Number of overdue tasks.
4. Number of completed tasks (`Done`).

Metrics must reflect the current database contents. Show useful empty states if there are no records.

### 5.2 Client Management (CRUD)

- Create a client.
- View the list of clients and their details.
- Edit client information.
- Delete a client after a confirmation prompt.
- Search clients by name, email, or company; case-insensitive matching is preferred.
- Deleting a client must **not** delete associated tasks.

### 5.3 Task Management (CRUD)

- Create a task, with required title and due date.
- View tasks, including due date, status, and linked client if any.
- Edit task details and change status among `To Do`, `In Progress`, and `Done`.
- Delete a task after a confirmation prompt.
- Filter the task list by status, due date, and linked client. Include an option to clear filters.
- Allow a task to be created or edited without linking it to a client.

### 5.4 User Interface

- A modern, readable business-style interface with navigation to **Dashboard**, **Clients**, and **Tasks**.
- Use a sidebar if practical, but prioritize clarity and functionality over visual complexity.
- Forms should have labels, validation feedback, and clear Save/Cancel actions.
- Use simple confirmation dialogs before deletion.
- Support common desktop browser sizes; basic responsive layout is desirable.
- Interface labels may be in English to match the course environment.

## 6. Suggested Routes

The following route map is a suggested Flask implementation. Equivalent routes are acceptable if documented and consistent.

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Dashboard |
| GET | `/clients` | Client list and search |
| GET, POST | `/clients/new` | Create client |
| GET, POST | `/clients/<int:client_id>/edit` | Edit client |
| POST | `/clients/<int:client_id>/delete` | Delete client, preserve tasks |
| GET | `/tasks` | Task list and filters |
| GET, POST | `/tasks/new` | Create task |
| GET, POST | `/tasks/<int:task_id>/edit` | Edit task |
| POST | `/tasks/<int:task_id>/delete` | Delete task |

- Use POST, not GET, for deletion.
- Validate data on the server, not only in the browser.
- Handle missing record IDs gracefully (e.g., a 404 page).
- Escape untrusted content in templates and use parameterized database queries.

## 7. Demo Data

On first database initialization only, insert a small set of **fictional** clients and tasks to demonstrate the interface. Include tasks in all three statuses, at least one overdue unfinished task, and at least one task with no client. Do not recreate demo data on every restart and do not overwrite user changes.

## 8. Full Product Vision and Development Roadmap

These requirements describe the **eventual AI Business Assistant**, not the Week 3 deliverable. Implement them in later iterations, subject to course scope, available integrations, and testing.

### 8.1 Planned product modules

| Module | Future capability |
|---|---|
| Mini CRM | Manage customers, contact information, notes, and customer-related activity |
| Task Management | Full CRUD, statuses, filtering, bulk editing, and optionally a Kanban view |
| Calendar & Scheduling | View and plan tasks, meetings, and events; connect planning with CRM and tasks |
| Reminders & Automation | Automatic reminders and repeatable business workflows |
| Business Analytics | Analyze customers, tasks, meetings, sales, and income; produce reports and improvement suggestions |
| AI Assistant | Conversational advice, data analysis, recommendations, and user-approved actions across modules |
| Industry Configuration | Allow later configuration of fields, views, and workflows for different small-business sectors |

### 8.2 AI interaction and action policy

- Support **text chat**, **quick-action buttons** (such as Find Client, Create Task, Analyse Tasks), and, later, **voice interaction**.
- AI should be able to read and analyze authorized business information from CRM, tasks, meetings, sales, and income modules as those modules become available.
- AI may **propose** creating tasks, updating customer records, or scheduling events. **Any change to stored data must be explicitly confirmed by the owner before execution.**
- Do not silently modify or delete records. For potentially destructive actions, show a clear preview and confirmation; preserve an audit trail in a future production version.
- AI-generated reports and recommendations should distinguish facts retrieved from stored records from suggestions or uncertain inferences.
- Add appropriate authentication, authorization, data minimization, and privacy controls before connecting AI to real customer or financial data.
- Do not simulate a live AI integration or claim that AI functionality works in Week 3.

### 8.3 Proposed phased delivery

1. **Week 3 — Functional foundation:** Dashboard, Mini CRM, task management, SQLite, search, filters, and demo data.
2. **Later — Usability and planning:** Calendar, bulk task editing, reminders, more polished UI, themes, animations, and interactive charts.
3. **Later — AI integration:** Text chat and quick actions; read-only analysis first, then confirmed write actions.
4. **Later — Expanded business intelligence:** Meetings, sales, income, reports, and voice interaction.
5. **Before real-world use:** Authentication, security review, privacy protections, deployment architecture, and sector-specific configuration.

The exact sequence after Week 3 can change with course assignments. Features listed as future capabilities must not be included in Week 3 acceptance tests.

## 9. Constraints and Out of Scope

### Week 3 constraints

- Local-only, single-user educational application.
- No authentication; not suitable for storing real customer data or public deployment.
- No cloud database, payment processing, external APIs, or Docker requirement.
- Avoid unnecessary complexity and large frameworks.

### Deferred from Week 3

- AI features, voice commands, and AI-controlled workflows.
- Calendar, meetings, reminders, bulk editing, and optional Kanban board.
- Advanced styling, animations, themes, interactive charts, and reports.
- Sales, income, financial analysis, and industry-specific configuration.
- Authentication and security hardening required before real-world use.

## 10. Week 3 Acceptance Criteria

The initial application is considered complete when:

- [ ] The application starts locally using the documented commands and opens in a browser.
- [ ] SQLite initializes automatically and persists changes across restarts.
- [ ] Fictional demo clients and tasks appear on first initialization only.
- [ ] Users can create, view, edit, and delete clients.
- [ ] Client validation requires a name plus phone or email.
- [ ] Client search works by name, email, and company.
- [ ] Users can create, view, edit, and delete tasks and change their statuses.
- [ ] Task validation requires title and due date; default status is `To Do`.
- [ ] Task filtering works by status, due date, and client.
- [ ] Dashboard metrics reflect stored data correctly.
- [ ] Deletion requires confirmation in the UI.
- [ ] Deleting a client retains its tasks and removes their client association.
- [ ] README includes setup, installation, startup, and test instructions.

## 11. Week 3 Git and Review Workflow

1. Save this specification as `docs/specification.md` in the project repository.
2. **Before generating application files**, create a feature branch (for example, `feature/business-assistant`).
3. Give the coding assistant this full specification and ask it to generate the initial multi-file scaffold.
4. Install dependencies, run the app, and fix any startup-blocking errors.
5. Commit the initial generated scaffold **before** feature improvements or refactoring. Keep the initial generated version identifiable in Git history.
6. Ask a **different assistant** to review the generated code and document findings in `docs/week03-review.md`.
7. Verify review findings manually; fix at least two issues in separate commits.
8. Push the branch, open a pull request with a meaningful description, and merge after review.

The Week 3 review and Git workflow are part of the learning exercise and are separate from the product feature checklist above.
