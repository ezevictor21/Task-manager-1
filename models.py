"""Database models for the Task Manager.

Two tables, as required by the brief:

* ``users`` - id, username, email, password_hash (+ created_at)
* ``tasks`` - id, user_id (FK -> users.id), title, description, due_date,
  status (+ priority, created_at, updated_at)

SQLAlchemy is used as the ORM, so every query is parameterised and safe
from SQL injection.
"""

from datetime import datetime

from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
bcrypt = Bcrypt()

# Allowed values. These are the single source of truth used by the
# validators, the routes and the templates.
STATUSES = ("To Do", "In Progress", "Completed")
PRIORITIES = ("Low", "Medium", "High")

TITLE_MAX = 100
DESCRIPTION_MAX = 500


class User(db.Model):
    """A registered user who owns tasks."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    tasks = db.relationship(
        "Task", backref="owner", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password):
        """Hash ``password`` with bcrypt and store the hash."""
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        """Return True if ``password`` matches the stored hash."""
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class Task(db.Model):
    """A task belonging to exactly one user."""

    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = db.Column(db.String(TITLE_MAX), nullable=False)
    description = db.Column(db.String(DESCRIPTION_MAX), nullable=True)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUSES[0])
    priority = db.Column(db.String(10), nullable=False, default=PRIORITIES[1])
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    @property
    def is_overdue(self):
        """True when the due date has passed and the task is not completed."""
        return self.status != "Completed" and self.due_date < datetime.utcnow().date()

    def __repr__(self):
        return f"<Task {self.id} '{self.title}' [{self.status}]>"
