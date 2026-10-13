# Task Manager

A web-based task management application built with **Python (Flask)**, **SQLite** and
**Tailwind CSS**. Registered users can create, view, edit and delete their own tasks,
filter and search them, and export them. Built as the Python Final Portfolio Project.

## Features

**Core**

- User registration with hashed passwords (bcrypt), email validation and case-insensitive unique usernames/emails
- Login / logout with Flask sessions; usernames are matched case-insensitively and all task pages require login
- Create, read, update and delete tasks (title, description, due date, status, priority)
- Dashboard with summary counts and a filter by status
- Delete confirmation prompt
- Server-side **and** client-side validation with user-friendly error messages
- Responsive layout (desktop and mobile) using Tailwind CSS via CDN
- Friendly 404 and 500 pages

**Advanced (brief asks for at least three)**

| Feature | Where |
|---|---|
| Task prioritisation (Low / Medium / High, colour-coded badges) | `models.py`, dashboard cards |
| Task sorting (due date, title, status, priority; asc / desc) | `/tasks?sort=…&order=…` |
| Search by title or description | `/tasks?q=…` |
| CSV export of all tasks | `/tasks/export` |
| JSON API (session-authenticated) | `GET /api/tasks` |

## Project structure

```
task-manager/
├── app.py              # Flask app, routes, application factory
├── config.py           # Config and TestConfig
├── models.py           # SQLAlchemy models: User, Task
├── validators.py       # Server-side form validation
├── requirements.txt
├── Procfile            # gunicorn start command (Render / Heroku)
├── render.yaml         # Render blueprint
├── REPORT.md           # 2-page project report
├── static/images/      # Logo
├── templates/          # Jinja2 + Tailwind templates
│   ├── base.html, index.html, dashboard.html, task_form.html
│   ├── login.html, register.html, 404.html, 500.html
└── tests/
    ├── conftest.py     # Fixtures (in-memory database, logged-in client)
    └── test_app.py     # 14 unit tests
```

## Setup

Requires Python 3.10 or newer.

```bash
# 1. Clone and enter the project
git clone https://github.com/ezevictor21/task-manager.git
cd task-manager

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app (the SQLite database is created automatically on first run)
python app.py
```

Open <http://127.0.0.1:5000>, register an account and start adding tasks.

To use your own secret key, set the environment variable `SECRET_KEY` before running.

## Running the tests

```bash
pytest tests/
```

All 14 tests run against an in-memory database and finish in a few seconds. Each test
has a comment above it describing its purpose.

## Deployment (Render)

The repo contains a `render.yaml` blueprint. In Render choose **New → Blueprint**, point it
at this repository and deploy. Render installs `requirements.txt`, generates a `SECRET_KEY`
and starts the app with `gunicorn app:app`.

Note: Render's free tier has an ephemeral filesystem, so the SQLite database resets when the
service restarts. That is acceptable for a demo; a hosted Postgres database can be plugged in
by setting `DATABASE_URL`.

## Known issues and limitations

- SQLite is single-file and resets on Render's free tier (see above).
- No password-reset flow. Adding one safely requires email delivery, which is out of scope.
- The JSON API is read-only and uses the browser session; a token-based scheme would be
  needed for use by other clients.
- No pagination. The dashboard is fine for hundreds of tasks but would need paging beyond that.
