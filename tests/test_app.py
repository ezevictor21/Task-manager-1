"""Unit tests for the Task Manager.

Run with::

    pytest tests/

Each test has a one-line comment above it explaining its purpose, as
required by the project brief. Fixtures live in ``conftest.py``.
"""

from models import Task, User, db
from tests.conftest import TASK, USER, login, register


# ---------------------------------------------------------------------- #
# User registration
# ---------------------------------------------------------------------- #

# Test 1: a user can register with valid details and is sent to the login page.
def test_registration_valid(client, app):
    response = register(client)
    assert response.status_code == 200
    assert b"Registration successful" in response.data
    with app.app_context():
        user = User.query.filter_by(username=USER["username"]).first()
        assert user is not None
        assert user.email == USER["email"]
        # Password must be stored as a hash, never in plain text.
        assert user.password_hash != USER["password"]
        assert user.check_password(USER["password"])


# Test 2: registration is rejected when the email address is malformed.
def test_registration_invalid_email(client, app):
    response = register(client, email="not-an-email")
    assert response.status_code == 400
    assert b"valid email" in response.data
    with app.app_context():
        assert User.query.count() == 0


# Test 3: registration is rejected when the two password fields differ.
def test_registration_password_mismatch(client, app):
    response = client.post("/register", data={**USER, "confirm_password": "different"})
    assert response.status_code == 400
    assert b"Passwords do not match" in response.data
    with app.app_context():
        assert User.query.count() == 0


# Test 4: a username or email that already exists cannot be registered twice.
def test_registration_duplicate_username(client, app):
    register(client)
    response = register(client, email="other@example.com")
    assert response.status_code == 400
    assert b"already taken" in response.data
    with app.app_context():
        assert User.query.count() == 1


# Test 4b: duplicate checks are case-insensitive for username and email.
def test_registration_duplicate_username_case_insensitive(client, app):
    register(client)
    response = register(client, username="TESTUSER", email="TEST@EXAMPLE.COM")
    assert response.status_code == 400
    assert b"already taken" in response.data
    assert b"already registered" in response.data
    with app.app_context():
        assert User.query.count() == 1


# ---------------------------------------------------------------------- #
# Login / logout / access control
# ---------------------------------------------------------------------- #

# Test 5: correct credentials log the user in and show the dashboard.
def test_login_success(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    assert b"Welcome back" in response.data
    assert b"My Tasks" in response.data


# Test 5b: usernames are matched case-insensitively when logging in.
def test_login_success_case_insensitive_username(client):
    register(client)
    response = login(client, username="TESTUSER")
    assert response.status_code == 200
    assert b"Welcome back" in response.data


# Test 6: a wrong password is rejected with an error and no session is created.
def test_login_failure(client):
    register(client)
    response = login(client, password="wrong-password")
    assert response.status_code == 401
    assert b"Invalid username or password" in response.data
    # Still locked out of protected pages afterwards.
    assert client.get("/tasks").status_code == 302


# Test 7: protected routes redirect guests to the login page.
def test_protected_route_requires_login(client):
    for path in ("/tasks", "/tasks/new", "/tasks/export", "/api/tasks"):
        response = client.get(path)
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------- #
# Task CRUD
# ---------------------------------------------------------------------- #

# Test 8: a logged-in user can create a task and it is linked to their account.
def test_task_creation(auth_client, app):
    response = auth_client.post("/tasks/new", data=TASK, follow_redirects=True)
    assert response.status_code == 200
    assert b"Task created successfully" in response.data
    with app.app_context():
        task = Task.query.first()
        assert task.title == TASK["title"]
        assert task.status == "To Do"
        assert task.priority == "High"
        assert task.owner.username == USER["username"]


# Test 9: invalid task input (missing title, bad date, unknown status) is rejected.
def test_task_creation_invalid_input(auth_client, app):
    bad = {**TASK, "title": "", "due_date": "31/01/2030", "status": "Bogus"}
    response = auth_client.post("/tasks/new", data=bad)
    assert response.status_code == 400
    assert b"Title is required" in response.data
    assert b"valid date" in response.data
    assert b"Status must be one of" in response.data
    with app.app_context():
        assert Task.query.count() == 0

    # Title longer than 100 characters is also rejected.
    response = auth_client.post("/tasks/new", data={**TASK, "title": "x" * 101})
    assert response.status_code == 400
    assert b"100 characters or fewer" in response.data


# Test 10: editing a task updates its fields in the database.
def test_task_update(auth_client, app):
    auth_client.post("/tasks/new", data=TASK)
    updated = {**TASK, "title": "Write final report", "status": "In Progress"}
    response = auth_client.post("/tasks/1/edit", data=updated, follow_redirects=True)
    assert response.status_code == 200
    assert b"Task updated successfully" in response.data
    with app.app_context():
        task = db.session.get(Task, 1)
        assert task.title == "Write final report"
        assert task.status == "In Progress"


# Test 11: deleting a task removes it from the database.
def test_task_deletion(auth_client, app):
    auth_client.post("/tasks/new", data=TASK)
    response = auth_client.post("/tasks/1/delete", follow_redirects=True)
    assert response.status_code == 200
    assert b"Task deleted" in response.data
    with app.app_context():
        assert Task.query.count() == 0
    # GET is not allowed for delete, so a plain link can never delete a task.
    assert auth_client.get("/tasks/1/delete").status_code == 405


# Test 12: a user cannot view, edit or delete another user's task.
def test_task_ownership_enforced(client, app):
    register(client)
    login(client)
    client.post("/tasks/new", data=TASK)
    client.get("/logout")

    register(client, username="intruder", email="intruder@example.com")
    login(client, username="intruder")
    assert client.get("/tasks/1/edit").status_code == 404
    assert client.post("/tasks/1/delete").status_code == 404
    with app.app_context():
        assert Task.query.count() == 1


# ---------------------------------------------------------------------- #
# Database queries: filtering, search, sorting
# ---------------------------------------------------------------------- #

# Test 13: the dashboard query returns only the user's tasks and honours filters.
def test_get_user_tasks_with_filters(auth_client, app):
    auth_client.post("/tasks/new", data={**TASK, "title": "Alpha", "status": "To Do"})
    auth_client.post("/tasks/new", data={**TASK, "title": "Beta", "status": "Completed",
                                         "priority": "Low"})
    auth_client.post("/tasks/new", data={**TASK, "title": "Gamma", "status": "In Progress"})

    with app.app_context():
        assert Task.query.filter_by(user_id=1).count() == 3

    page = auth_client.get("/tasks?status=Completed").data
    assert b"Beta" in page and b"Alpha" not in page and b"Gamma" not in page

    page = auth_client.get("/tasks?priority=High").data
    assert b"Alpha" in page and b"Gamma" in page and b"Beta" not in page

    page = auth_client.get("/tasks?q=gam").data
    assert b"Gamma" in page and b"Alpha" not in page

    page = auth_client.get("/tasks?sort=title&order=desc").data
    assert page.index(b"Gamma") < page.index(b"Beta") < page.index(b"Alpha")


# Test 14: CSV export and the JSON API return the user's tasks.
def test_export_and_api(auth_client):
    auth_client.post("/tasks/new", data=TASK)

    csv_response = auth_client.get("/tasks/export")
    assert csv_response.status_code == 200
    assert csv_response.mimetype == "text/csv"
    assert b"Write report" in csv_response.data

    api_response = auth_client.get("/api/tasks")
    assert api_response.status_code == 200
    payload = api_response.get_json()
    assert len(payload) == 1
    assert payload[0]["title"] == TASK["title"]
    assert payload[0]["due_date"] == TASK["due_date"]
