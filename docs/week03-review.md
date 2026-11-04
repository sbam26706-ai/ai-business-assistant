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

## What I fixed, and why

Follow-up verified on **2026-11-04**, against current commit `d2e9106`. The sections above preserve the original review and its evidence. Their descriptions of the old code and four-test suite are historical; the updates below describe the current implementation.

### Finding 2: isolated automated test databases

I fixed the import-time database initialization in commit **`523e0e7`**, dated 2026-10-30, titled **`fix: isolate automated tests from application database`**. Inspection of the commit diff confirms that `app = create_app()` moved inside `if __name__ == "__main__":` in `app.py`. Importing the factory for tests no longer creates an application or opens its normal database. Running `python app.py` still creates the application and starts it on `127.0.0.1:5000` with the same options.

This fix matters because tests must not initialize, read, or modify the owner's normal database. `BusinessAssistantTests.setUp()` explicitly supplies a database path inside a separate `TemporaryDirectory` for each test; the seeding test also uses a database in that directory. Test cleanup removes these disposable databases.

The same commit adds `DatabaseIsolationTests.test_imports_and_suite_never_open_normal_database`. It starts fresh Python subprocesses, guards `sqlite3.connect` against both the default `data/app.db` path and an environment-configured normal database path, then imports `app` and `test_app` and runs the functional tests. It checks two cases: a nonexistent configured database remains absent, and an existing disposable sentinel file remains byte-for-byte unchanged. The connection guard catches attempted reads as well as writes through SQLite; the check is stronger than merely comparing file contents afterward. The sentinel is a stand-in for an existing database, not real application data.

### Finding 5: server-side client email validation

I fixed the reported malformed-email acceptance in commit **`0621a92`**, dated 2026-10-30, titled **`fix: validate client email addresses`**. Its diff replaces the permissive expression in `app.py` with validation for a common unquoted ASCII local part and dot-separated domain labels, and limits the local part to 64 characters. Existing total-address length checking remains. Both client creation and editing call the shared `validate_client()` function, so the rules apply on the server in both routes.

This prevents values such as `a@b..com` and `a@b.c,d` from being stored even when browser validation is bypassed. Email remains optional when a phone is provided, as required by specification section 4.1. A valid email can still be the only contact method; supplying neither phone nor email is rejected. Submitted values are still trimmed, and an empty email is stored as `NULL`.

The commit adds `test_client_email_validation_on_create_and_edit`. It checks valid addresses, plus addressing and subdomains, trimmed values, empty and whitespace-only values, and malformed addresses on both routes. It verifies that invalid submissions leave the client records unchanged, that phone-only and email-only contacts are supported, and that a contact method is still required. All database operations in these tests use the temporary test database. The validator does not attempt mailbox delivery checks and does not support every possible standards-valid or internationalized email syntax.

### Verified history and test results

I checked both fix commits using `git show` and confirmed their presence in the current branch history with `git log`. Each commit contains the corresponding application change and regression test in `app.py` and `test_app.py`. The original review is recorded in `d14784d`, before these two fixes. These are existing commits; none was created during this documentation update.

I reran the current suite with:

```powershell
.\.venv\Scripts\python.exe -B -m unittest -v
```

Observed result on 2026-11-04:

```text
test_client_email_validation_on_create_and_edit ... ok
test_client_validation_search_and_task_preserving_delete ... ok
test_dashboard_metrics_use_current_data ... ok
test_demo_data_is_seeded_once_and_has_required_examples ... ok
test_task_validation_filters_and_crud ... ok
test_imports_and_suite_never_open_normal_database ... ok

Ran 6 tests in 2.700s
OK
```

This is a fresh result for the current code, not a claim that Git stores historical test-run results. The isolation regression also executes the functional tests in its guarded subprocesses. The suite uses disposable databases and does not need to open the normal application database.

## What I am knowingly leaving, and why

The following three findings remain unresolved. I checked their current code paths and repeated the original request checks using a disposable temporary SQLite database, with connections outside that temporary directory blocked. No normal application database was opened. Passing the existing suite does not mean these outstanding cases are covered or fixed.

| Finding | Current evidence and risk | Reason for deferral and follow-up |
|---|---|---|
| **1. CSRF (Medium)** | Create, edit, and delete routes still lack CSRF tokens and origin validation. A simulated cross-origin POST to `/clients/new` returned HTTP 302 and saved one client in the disposable database. A foreign page could bypass the application's JavaScript delete confirmation if the browser permits the request to localhost. A working browser exploit has not been demonstrated. | I am deferring this security work for the local educational MVP, which the specification restricts to fictional data and forbids deploying publicly or using for real customer information. Loopback binding reduces exposure but does not eliminate this risk. Before real-world use, add server-validated CSRF tokens to all write forms and verify cross-origin rejection alongside the wider security review. |
| **3. Oversized numeric IDs (Medium)** | `int()` conversion and record lookups still lack SQLite integer-range checks. GET `/tasks?client_id=9223372036854775808`, GET `/clients/9223372036854775808/edit`, and a valid task POST containing that client ID each raised `OverflowError`. Outside testing, these are unhandled server errors. The checks did not demonstrate SQL injection or database corruption. | The normal interface supplies stored record IDs, so these failures require crafted requests or manually altered URLs rather than ordinary use. I prioritized database isolation and client data validation for this exercise. This remains an error-handling and validation gap; add consistent ID range checks and regression tests in a later fix. |
| **4. Missing task status default (Low)** | `task_form_data()` still reads an absent status as an empty string, and `validate_task()` rejects it. A task POST with a valid title and date but no status returned HTTP 200 with “Choose a valid task status.” The normal creation form already selects and submits `To Do`. | I am deferring this narrow server-side default inconsistency because the supported browser workflow supplies the value and works. It remains a specification gap for submissions that omit status. Later, apply `To Do` when status is omitted on creation while continuing to reject unsupported explicit values; decide edit behavior separately. |

These are conscious scope and priority decisions for the assignment, not claims that local use makes the issues harmless or that every acceptance criterion is fully satisfied. The specification explicitly postpones production security hardening; it does not explicitly waive ID validation or the task default.

## What the reviewer got wrong

**No actual false positives could be verified among the original five findings.** Reviewing the original code in Git history and the current implementation supports the reported behaviors. A finding that has since been fixed is not a reviewer mistake. The useful corrections are qualifications of scope and evidence:

| Original finding | Reassessment |
|---|---|
| **1. CSRF** | The missing server-side protection is real and remains unresolved. The Flask test-client result establishes server acceptance of a simulated cross-origin request, not successful exploitation by an actual browser. Browser restrictions on local access may affect exploitability. Treating the original check as proof of a browser attack would overstate its evidence; the historical finding already notes this limitation. |
| **2. Test isolation** | Correct at review time: the original module created the application and initialized the normal database during test import. The history confirms that `523e0e7` removed this side effect. This is a completed fix, not a false positive. The original finding did not claim that every run necessarily changed existing customer records. |
| **3. Oversized numeric IDs** | Correct and still reproducible. The evidenced outcome is an unhandled integer-binding exception and server error. Claims of SQL injection or stored-data corruption would go beyond the evidence; neither was established by the original review. |
| **4. Missing status default** | The omitted-field behavior is real, but its significance is limited. The UI and SQLite schema already default to `To Do`; the issue concerns the server's handling of an omitted form field. The specification requires a default but does not define a general API contract for partial submissions. This supports treating it as a low-severity backend consistency concern rather than a broken ordinary UI workflow. It is not a verified false positive. |
| **5. Email validation** | Correct for the original regex: it accepted the cited malformed addresses. Commit `0621a92` fixes those cases, and current route tests verify rejection on both create and edit. The new validator's limited email syntax support and lack of mailbox verification are implementation boundaries, not evidence that the original finding was wrong. |

The original coverage paragraph also describes the suite at review time. There are now six test methods, including regressions for isolation and email validation. That historical four-test description has been preserved rather than rewritten as though the new tests existed during the initial review.
