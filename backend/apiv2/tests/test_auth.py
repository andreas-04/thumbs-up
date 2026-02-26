"""
Unit tests for the TokenAuth class (core/auth.py).
"""

from datetime import datetime, timedelta, timezone

import jwt


class TestHashAndVerifyPassword:
    def test_hash_password_returns_string(self, auth_instance):
        hashed = auth_instance.hash_password("secret")
        assert isinstance(hashed, str)
        assert hashed != "secret"

    def test_verify_password_correct(self, auth_instance):
        hashed = auth_instance.hash_password("secret")
        assert auth_instance.verify_password("secret", hashed) is True

    def test_verify_password_incorrect(self, auth_instance):
        hashed = auth_instance.hash_password("secret")
        assert auth_instance.verify_password("wrong", hashed) is False

    def test_verify_password_invalid_hash(self, auth_instance):
        assert auth_instance.verify_password("secret", "not-a-hash") is False


class TestGenerateAndValidateToken:
    def test_generate_token_returns_string(self, auth_instance):
        token = auth_instance.generate_token()
        assert isinstance(token, str)

    def test_validate_valid_token(self, auth_instance):
        token = auth_instance.generate_token(user_id="u1", permissions=["read"])
        payload = auth_instance.validate_token(token)
        assert payload is not None
        assert payload["user_id"] == "u1"
        assert "read" in payload["permissions"]

    def test_validate_expired_token(self, auth_instance):
        # Manually create an expired token
        payload = {
            "user_id": "u1",
            "iat": datetime.utcnow() - timedelta(hours=2),
            "exp": datetime.utcnow() - timedelta(hours=1),
        }
        token = jwt.encode(payload, auth_instance.secret_key, algorithm=auth_instance.algorithm)
        assert auth_instance.validate_token(token) is None

    def test_validate_token_wrong_key(self, auth_instance):
        token = auth_instance.generate_token()
        # Validate with a different secret key
        from core.auth import TokenAuth

        other = TokenAuth(secret_key="different-key")
        assert other.validate_token(token) is None

    def test_validate_malformed_token(self, auth_instance):
        assert auth_instance.validate_token("not.a.token") is None


class TestGuestTokens:
    def test_generate_guest_token_read_write(self, auth_instance):
        token = auth_instance.generate_guest_token(read_only=False)
        payload = auth_instance.validate_token(token)
        assert "read" in payload["permissions"]
        assert "write" in payload["permissions"]

    def test_generate_guest_token_read_only(self, auth_instance):
        token = auth_instance.generate_guest_token(read_only=True)
        payload = auth_instance.validate_token(token)
        assert "read" in payload["permissions"]
        assert "write" not in payload["permissions"]

    def test_guest_token_tracked(self, auth_instance):
        token = auth_instance.generate_guest_token()
        active = auth_instance.get_active_guest_tokens()
        assert len(active) == 1
        assert active[0]["token"] == token

    def test_revoke_guest_token(self, auth_instance):
        auth_instance.generate_guest_token()
        active = auth_instance.get_active_guest_tokens()
        token_id = active[0]["id"]
        assert auth_instance.revoke_guest_token(token_id) is True
        assert auth_instance.get_active_guest_tokens() == []

    def test_revoke_nonexistent_token(self, auth_instance):
        assert auth_instance.revoke_guest_token("nonexistent") is False

    def test_get_active_tokens_cleans_expired(self, auth_instance):
        # Manually insert an expired token
        past = datetime.utcnow() - timedelta(hours=2)
        auth_instance.active_guest_tokens["expired-id"] = {
            "token": "dummy",
            "created": past,
            "expires": past,
        }
        assert auth_instance.get_active_guest_tokens() == []


class TestIsAdmin:
    def test_is_admin_true(self, auth_instance):
        payload = {
            "user_id": "admin",
            "role": "admin",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        token = jwt.encode(payload, auth_instance.secret_key, algorithm=auth_instance.algorithm)
        assert auth_instance.is_admin(token) is True

    def test_is_admin_false_for_user(self, auth_instance):
        token = auth_instance.generate_token(user_id="u1")
        assert auth_instance.is_admin(token) is False

    def test_is_admin_false_for_invalid_token(self, auth_instance):
        assert not auth_instance.is_admin("bad-token")


class TestGenerateSessionToken:
    def test_admin_session_expires_in_2h(self, app, admin_user):
        from core.server import auth

        token = auth.generate_session_token(admin_user)
        payload = auth.validate_token(token)
        assert payload is not None
        assert payload["role"] == "admin"
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        diff_hours = (exp - iat).total_seconds() / 3600
        assert abs(diff_hours - 2) < 0.01

    def test_user_session_uses_configured_expiry(self, app, regular_user):
        from core.server import auth

        token = auth.generate_session_token(regular_user)
        payload = auth.validate_token(token)
        assert payload is not None
        assert payload["role"] == "user"
