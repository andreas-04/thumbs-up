"""
Shared pytest fixtures for ThumbsUp backend tests.
"""

import os
import secrets
import sys

import pytest

# Ensure apiv2 is on the path so imports work the same way as in production
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Randomly generated at import time so no hardcoded secret-like literals exist in source.
_TEST_JWT_SECRET = secrets.token_hex(32)

# Set required env vars BEFORE importing server (server.py exits if ADMIN_PIN missing,
# and DATABASE_URI must point to an in-memory DB so tests don't touch the filesystem).
os.environ["ADMIN_PIN"] = secrets.token_hex(4)
os.environ["DATABASE_URI"] = "sqlite:///:memory:"


@pytest.fixture
def app():
    """Create a Flask test application with an in-memory SQLite database."""
    from core.server import app as flask_app
    from models import SystemSettings, db

    flask_app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        }
    )

    with flask_app.app_context():
        db.create_all()

        # Seed required SystemSettings row so endpoints don't 404
        settings = SystemSettings(mode="open", auth_method="email+password", tls_enabled=False)
        db.session.add(settings)
        db.session.commit()

        yield flask_app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Return a test client for the Flask app."""
    return app.test_client()


@pytest.fixture
def auth_instance():
    """Return a standalone TokenAuth instance (no Flask context needed)."""
    from core.auth import TokenAuth

    return TokenAuth(secret_key=_TEST_JWT_SECRET, token_expiry_hours=1)


@pytest.fixture
def admin_user(app):
    """Create an admin user and return it."""
    from core.auth import TokenAuth
    from models import User, db

    _auth = TokenAuth(secret_key=_TEST_JWT_SECRET)
    user = User(
        email="admin@test.com",
        password_hash=_auth.hash_password("adminpass"),
        role="admin",
        is_default_pin=False,
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def regular_user(app):
    """Create a regular user and return it."""
    from core.auth import TokenAuth
    from models import User, db

    _auth = TokenAuth(secret_key=_TEST_JWT_SECRET)
    user = User(
        email="user@test.com",
        password_hash=_auth.hash_password("userpass"),
        role="user",
        is_default_pin=False,
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def admin_token(app, admin_user):
    """Return a valid JWT token for the admin user."""
    from core.server import auth

    return auth.generate_session_token(admin_user)


@pytest.fixture
def user_token(app, regular_user):
    """Return a valid JWT token for the regular user."""
    from core.server import auth

    return auth.generate_session_token(regular_user)


@pytest.fixture
def storage_dir(tmp_path):
    """Return a temporary storage directory."""
    return str(tmp_path)
