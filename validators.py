"""Server-side validation for registration, login and task forms.

Each function takes the raw form values and returns a tuple of
``(cleaned_data, errors)`` where ``errors`` is a list of user-friendly
messages. An empty list means the input is valid. Validation lives here,
away from the routes, so it can be unit-tested on its own and reused.
"""

import re
from datetime import date, datetime

from models import DESCRIPTION_MAX, PRIORITIES, STATUSES, TITLE_MAX

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,50}$")
PASSWORD_MIN = 6


def validate_registration(form):
    """Validate a registration form.

    Checks that every field is present, the username is 3-50 letters,
    digits or underscores, the email looks like an email, the password is
    long enough and both password fields match.
    """
    data = {
        "username": (form.get("username") or "").strip(),
        "email": (form.get("email") or "").strip().lower(),
        "password": form.get("password") or "",
        "confirm_password": form.get("confirm_password") or "",
    }
    errors = []

    if not USERNAME_RE.match(data["username"]):
        errors.append("Username must be 3-50 characters using letters, numbers or underscores.")
    if not EMAIL_RE.match(data["email"]):
        errors.append("Please enter a valid email address.")
    if len(data["password"]) < PASSWORD_MIN:
        errors.append(f"Password must be at least {PASSWORD_MIN} characters long.")
    if data["password"] != data["confirm_password"]:
        errors.append("Passwords do not match.")

    return data, errors


def validate_login(form):
    """Validate a login form: both fields must be present."""
    data = {
        "username": (form.get("username") or "").strip(),
        "password": form.get("password") or "",
    }
    errors = []
    if not data["username"] or not data["password"]:
        errors.append("Username and password are required.")
    return data, errors


def parse_date(value):
    """Parse an ISO date string (YYYY-MM-DD). Return a ``date`` or ``None``."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def validate_task(form):
    """Validate a task create/edit form against the brief's rules.

    * title: required, max 100 characters
    * description: optional, max 500 characters
    * due_date: required, YYYY-MM-DD
    * status: one of STATUSES
    * priority: one of PRIORITIES
    """
    data = {
        "title": (form.get("title") or "").strip(),
        "description": (form.get("description") or "").strip(),
        "due_date_raw": (form.get("due_date") or "").strip(),
        "status": (form.get("status") or STATUSES[0]).strip(),
        "priority": (form.get("priority") or PRIORITIES[1]).strip(),
    }
    errors = []

    if not data["title"]:
        errors.append("Title is required.")
    elif len(data["title"]) > TITLE_MAX:
        errors.append(f"Title must be {TITLE_MAX} characters or fewer.")

    if len(data["description"]) > DESCRIPTION_MAX:
        errors.append(f"Description must be {DESCRIPTION_MAX} characters or fewer.")

    data["due_date"] = parse_date(data["due_date_raw"])
    if data["due_date"] is None:
        errors.append("Due date is required and must be a valid date (YYYY-MM-DD).")

    if data["status"] not in STATUSES:
        errors.append("Status must be one of: " + ", ".join(STATUSES) + ".")

    if data["priority"] not in PRIORITIES:
        errors.append("Priority must be one of: " + ", ".join(PRIORITIES) + ".")

    return data, errors


def today_iso():
    """Today's date as YYYY-MM-DD, used to pre-fill the due date field."""
    return date.today().isoformat()
