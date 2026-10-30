# Week 3 Mini CRM review

Review baseline: `docs/specification.md`.

Scope: Flask routes, SQLite initialization and queries, HTML templates, JavaScript, CSS, README, and automated tests. The review focuses on the local, single-user Week 3 application. Authentication and future AI/calendar features are outside its acceptance criteria.

## Verification and limitations

The findings below distinguish observed behavior, issues established by static inspection, and potential exploitation risks. Targeted checks during the original review used an in-memory SQLite database with import-time application initialization suppressed. They did not change the application database or project files. The normal test suite was not run because its import path can initialize the normal database, as described in finding 2. No browser exploit was tested.

This document records that earlier review. No application code was changed and no tests were run while creating this document.

## 1. Cross-site POST requests lack server-side protection

- **Severity:** Medium within the local prototype's scope.
- **Status:** Verified acceptance of a simulated cross-origin request; browser exploitation is a potential risk, not verified.
- **Affected files:** `app.py` (create, edit, and delete routes, including lines 84, 144, 213, and 297); `templates/clients.html` (delete form); `templates/tasks.html` (delete form); `static/app.js` (confirmation handler).

**Explanation:** State-changing routes do not require a CSRF token or validate the request origin. Delete confirmation is implemented only by JavaScript attached to the application's own forms. A form on another page would not execute that confirmation handler. Because the application is unauthenticated, an attacker does not need a session cookie to authorize a write.

**Evidence:** An isolated Flask test-client POST to `/clients/new` containing a valid name and phone, with `Origin: https://example.invalid` and `Sec-Fetch-Site: cross-site`, returned HTTP 302 and inserted one client into the in-memory database. This verifies server acceptance of those headers; it does not establish that every browser will permit a remote website to submit to localhost. Browser restrictions on local-network access can affect exploitation.

**How to verify:** In a disposable application instance, submit a form from another origin to `/clients/new`. For deletion, target a known disposable record's delete endpoint. Check whether the database changes without the application's confirmation dialog. Do not perform this check against records that must be retained.

**Recommended fix:** Add server-validated CSRF tokens to every state-changing form and reject missing or invalid tokens. A small documented CSRF library is an option; origin checks can provide additional protection. Keep deletion confirmation for usability, and retain the loopback-only binding. Verify protection for create, edit, and delete requests.

## 2. Test imports initialize the normal application database

- **Severity:** Medium.
- **Status:** Verified by static inspection of the import and initialization path; not reproduced against the workspace database.
- **Affected files:** `test_app.py:6`; `app.py:543` (module-level application creation); `app.py:327` (database initialization); `README.md` (test-isolation assurance).

**Explanation:** `test_app.py` imports `create_app` and `get_db` from `app.py`. Importing that module executes `app = create_app()`, which calls `initialize_database()` before test setup selects a temporary database. The default target is `data/app.db`, or the database selected by `DATABASE_PATH`.

On a fresh checkout, the documented test command can therefore create and seed the normal database. With an existing database, initialization SQL still runs; if the demo-data marker is missing, initialization can insert demo records. Ordinary already-initialized records are not necessarily changed, but the suite does not provide the isolation promised by the README.

**Evidence:** The source shows the direct chain: test import → module-level `create_app()` → `initialize_database(app)` → schema creation and conditional seeding. Temporary database configuration occurs later in `setUp()` and cannot prevent the earlier initialization.

**How to verify:** In a disposable checkout without `data/app.db`, run the README's test command and check whether that file is created. Alternatively, point `DATABASE_PATH` to a disposable nonexistent database before importing the test module and inspect that location afterward.

**Recommended fix:** Avoid database initialization as a side effect of importing the module used by tests. Move executable application creation to a separate entry point or use an explicitly invoked application factory. Ensure test configuration is supplied before any database initialization. Keep the README's isolation assurance only once the documented command satisfies it.

## 3. Oversized numeric IDs cause unhandled errors

- **Severity:** Medium.
- **Status:** Verified with isolated in-memory requests.
- **Affected files:** `app.py:180` (client filter conversion); `app.py:474` and `app.py:504` (task client parsing and lookup); `app.py:524` and `app.py:534` (record lookups).

**Explanation:** Python accepts integers larger than SQLite's signed 64-bit integer range. IDs are converted or accepted by routing without checking that range before being bound to SQL parameters. Such values raise `OverflowError`, producing a server error instead of clear validation feedback or a graceful 404. This conflicts with the specification's server-validation and missing-ID error-handling expectations.

**Evidence:** Each of these isolated requests raised `OverflowError: Python int too large to convert to SQLite INTEGER`:

- GET `/tasks?client_id=9223372036854775808`.
- GET `/clients/9223372036854775808/edit`.
- POST `/tasks/new` with a valid title, due date, status, and `client_id=9223372036854775808`.

Testing mode propagated the exception; normal request handling would return HTTP 500. Other numeric record routes use the same vulnerable binding pattern, although each route was not separately exercised.

**How to verify:** Repeat those requests in a disposable instance. For the POST, use `title=Example`, `due_date=2026-12-01`, and `status=To Do` so earlier validation does not hide the ID error.

**Recommended fix:** Validate IDs against the supported positive SQLite integer range before querying. Give invalid form/filter IDs clear validation feedback and handle out-of-range route IDs as missing records. Apply the same rule consistently to client and task lookups.

## 4. Omitted task status does not receive the specified default

- **Severity:** Low.
- **Status:** Verified with an isolated in-memory request; the ordinary browser form supplies the default correctly.
- **Affected files:** `app.py:487` (status parsing); `app.py:501` (status validation); `templates/task_form.html` (UI default).

**Explanation:** The specification defines the default status as `To Do`. The HTML form selects that value for new tasks, but server parsing uses an empty string when `status` is absent and validation then rejects it. The SQLite default cannot apply because validation happens first and the insert explicitly supplies a status.

**Evidence:** POST `/tasks/new` with `title=Default status` and `due_date=2026-12-01`, omitting `status`, returned HTTP 200 with “Choose a valid task status” instead of creating a task. This is a server-side default mismatch; it does not prevent normal submissions from the current UI.

**How to verify:** Submit that request in a disposable instance and confirm that no task is saved. Compare with a request explicitly supplying `status=To Do`.

**Recommended fix:** Default an omitted status to `To Do` when creating a task, while continuing to reject explicitly unsupported status values. Decide separately whether a missing status on edit should preserve the existing value or produce validation feedback.

## 5. Email validation accepts malformed domains

- **Severity:** Low.
- **Status:** Verified at the server validation-function level; a full route submission was not exercised for these examples.
- **Affected files:** `app.py:20` (`EMAIL_PATTERN`); `app.py:455` (email validation); `templates/client_form.html` (browser email input).

**Explanation:** The regular expression requires an `@`, a later dot, and no whitespace, but does not adequately validate domain syntax. It accepts addresses with consecutive domain dots or a comma in the domain, weakening the specification's requirement to validate email format when provided. Browser validation is not a substitute for server validation.

**Evidence:** Direct calls to `validate_client()` with a valid name, no phone, and either `a@b..com` or `a@b.c,d` returned `None`, meaning validation succeeded. Static inspection shows that the create and edit routes use this validator before saving.

**How to verify:** In a disposable instance, POST either address to `/clients/new` with a valid name and no phone, bypassing browser validation. Inspect the response and saved record. Repeat on edit if verifying both routes.

**Recommended fix:** Use a documented email-format validator, or a carefully bounded validation approach that rejects malformed domain labels and prohibited characters without unnecessarily rejecting valid addresses. Format checking does not need to verify mailbox existence or perform external network calls.

## Existing coverage and compliant behavior

The four existing test methods cover useful CRUD paths, combined task filtering, dashboard metrics, one-time seeding, and preserving tasks after client deletion. None directly covers the five findings above. Dedicated checks are also absent for malformed dates, invalid emails, missing record IDs, POST-only deletion, template escaping, and browser confirmation behavior. These are coverage observations, not additional verified application defects.

Static inspection found parameterized SQL, foreign-key enforcement on connections, `ON DELETE SET NULL`, normal Jinja escaping of displayed data, and consistent overdue calculations based on the current local date. These support the core Week 3 requirements, but do not constitute a complete runtime or browser acceptance test.
