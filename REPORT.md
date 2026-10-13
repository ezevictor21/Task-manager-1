# Task Manager - Project Report

## 1. Overview

The Task Manager is a Flask web application that lets registered users manage personal
tasks. It was built to meet the Python Final Portfolio brief: Flask backend, SQLite
database, Tailwind CSS frontend, secure authentication, server-side validation, unit tests
and deployment to Render.

## 2. Database schema

Two tables, linked by a foreign key.

**users**

| Column | Type | Notes |
|---|---|---|
| id | INTEGER | primary key |
| username | VARCHAR(50) | unique, not null |
| email | VARCHAR(120) | unique, not null |
| password_hash | VARCHAR(128) | bcrypt hash, never plain text |
| created_at | DATETIME | default now |

**tasks**

| Column | Type | Notes |
|---|---|---|
| id | INTEGER | primary key |
| user_id | INTEGER | foreign key → users.id, indexed, cascade delete |
| title | VARCHAR(100) | not null |
| description | VARCHAR(500) | nullable |
| due_date | DATE | not null |
| status | VARCHAR(20) | "To Do", "In Progress" or "Completed" |
| priority | VARCHAR(10) | "Low", "Medium" or "High" |
| created_at, updated_at | DATETIME | updated_at refreshes on every edit |

One user has many tasks. Deleting a user cascades to their tasks. Every query goes through
SQLAlchemy, so all SQL is parameterised and safe from injection.

## 3. Key design decisions

**Application factory.** `create_app(config)` builds the app from a config class. The test
suite passes `TestConfig`, which points at an in-memory SQLite database, so tests are fast
and never touch the real database file.

**Validation in its own module.** `validators.py` turns raw form data into cleaned values
plus a list of error messages. Routes stay short, and the rules (title ≤ 100 characters,
description ≤ 500, due date required and in ISO format, status and priority restricted to
fixed lists, email matched by regex) are testable without a browser. The same limits are
mirrored as HTML attributes (`required`, `maxlength`, `type="date"`) for client-side
feedback, but the server is the authority.

**Allowed values as constants.** `STATUSES` and `PRIORITIES` in `models.py` are injected
into every template through a context processor. Changing a status name is a one-line edit.

**Ownership checks return 404, not 403.** `get_owned_task_or_404` looks up a task by id and
user id together. A user who guesses another user's task id gets "not found" rather than
confirmation that the task exists.

**Deletes are POST-only** with a JavaScript `confirm()` prompt, so a crawler or a stray link
can never remove data.

**Session security.** Cookies are `HttpOnly` and `SameSite=Lax`. `Secure` is switched on
automatically when running on Render (HTTPS). The session is cleared on login to prevent
session fixation.

**Tailwind via CDN.** As required by the brief. A small inline script toggles the mobile
navigation menu; everything else is utility classes.

## 4. Challenges and solutions

- **Bad input crashed the app.** An early version parsed the due date with `strptime` and
  no error handling, so a date typed in the wrong format produced a 500. Moving parsing into
  `parse_date()` with a `try/except` and returning a friendly message fixed it.
- **Database length limits were not enforced.** SQLite ignores `VARCHAR(100)`, so over-long
  titles were being saved. Explicit length checks in the validator solved this.
- **A broken requirements file.** `pip freeze` had produced a version pin that did not exist
  on PyPI, which broke installation and the Render build. The file was regenerated from a
  clean virtual environment and verified with a fresh install.
- **Testing with a shared database.** Tests originally interfered with each other. Switching
  to the factory pattern with a per-test in-memory database made every test independent.

## 5. Advanced features implemented

1. **Prioritisation** - Low / Medium / High stored per task and shown as colour-coded badges.
2. **Sorting** - server-side `ORDER BY` on due date, title, status or priority, ascending or
   descending, chosen from the dashboard form.
3. **Search** - case-insensitive `LIKE` match on title or description.
4. **CSV export** - `/tasks/export` streams the user's tasks with Python's `csv` module.
5. **RESTful API** - `GET /api/tasks` returns the user's tasks as JSON, protected by the
   same session login as the HTML pages.

## 6. Testing

Fourteen pytest tests in `tests/test_app.py` cover valid and invalid registration, duplicate
accounts, successful and failed login, protected routes, task creation, invalid task input,
update, deletion, ownership enforcement, filtering/search/sorting queries, and the export
and API endpoints. They run with a single command, `pytest tests/`.

## 7. Reflection

The project pulled together the full web stack: routing and templating in Flask, relational
modelling with SQLAlchemy, password hashing, session handling, input validation, responsive
layout and automated testing. The biggest lesson was that the browser cannot be trusted:
HTML `required` and `maxlength` are conveniences, and every rule must be enforced again on
the server. The second was the value of the application factory, which made the test suite
both reliable and fast. The result is a small but complete application that I can extend
with categories, pagination or email reminders.
