"""Application configuration.

Settings are read from environment variables where it matters (secret key,
database location) so the same code runs locally, in tests and on Render.
"""

import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Default configuration used for local development and production."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'task_manager.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session hardening. SESSION_COOKIE_SECURE is only switched on when the
    # app runs behind HTTPS (Render sets the RENDER environment variable).
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = bool(os.environ.get("RENDER"))
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)


class TestConfig(Config):
    """Configuration used by the test suite: in-memory database, no secrets."""

    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
