"""Shared pytest fixtures.

Every test gets a brand-new application instance backed by an in-memory
SQLite database, so tests never touch task_manager.db and never affect
each other.
"""

import os
import sys

import pytest

# Make the project root importable when running ``pytest tests/``.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402
from config import TestConfig  # noqa: E402
from models import db  # noqa: E402

USER = {"username": "testuser", "email": "test@example.com", "password": "testpass123"}
TASK = {
    "title": "Write report",
    "description": "Two pages covering the schema and design decisions.",
    "due_date": "2030-01-31",
    "status": "To Do",
    "priority": "High",
}


@pytest.fixture
def app():
    """A fresh app with empty in-memory tables."""
    application = create_app(TestConfig)
    with application.app_context():
        db.drop_all()
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Unauthenticated test client."""
    return app.test_client()


def register(client, **overrides):
    """Register the default test user (or an override) and return the response."""
    data = {**USER, "confirm_password": USER["password"], **overrides}
    if "confirm_password" not in overrides and "password" in overrides:
        data["confirm_password"] = overrides["password"]
    return client.post("/register", data=data, follow_redirects=True)


def login(client, username=USER["username"], password=USER["password"]):
    """Log in and return the response."""
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=True)


@pytest.fixture
def auth_client(client):
    """A client that is already registered and logged in."""
    register(client)
    login(client)
    return client
