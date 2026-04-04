"""
Tests for the certificate revocation and re-issue endpoints.
"""

from datetime import UTC
from unittest.mock import patch


class TestRevokeCert:
    """Test POST /api/v1/users/<id>/revoke-cert."""

    def _seed_user_with_cert(self, app):
        """Create a user with cert metadata populated."""
        from core.auth import TokenAuth
        from models import User, db

        _auth = TokenAuth(secret_key="test")
        user = User(
            email="certuser@test.com",
            password_hash=_auth.hash_password("pass"),
            role="user",
            is_default_pin=False,
            is_approved=True,
            cert_serial_number="abcdef1234",
            cert_revoked=False,
        )
        db.session.add(user)
        db.session.commit()
        return user

    @patch("core.server.generate_crl", return_value=b"fake-crl")
    @patch("core.server.update_crl_file")
    def test_revoke_cert_success(self, mock_update_crl, mock_gen_crl, client, app, admin_user, admin_token):
        user = self._seed_user_with_cert(app)

        resp = client.post(
            f"/api/v1/users/{user.id}/revoke-cert",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["revokedSerial"] == "abcdef1234"
        assert data["user"]["certRevoked"] is True

        # Verify DB state
        from models import RevokedCertificate, User, db

        db_user = db.session.get(User, user.id)
        assert db_user.cert_revoked is True
        assert db_user.cert_serial_number is None

        revoked = RevokedCertificate.query.filter_by(serial_number="abcdef1234").first()
        assert revoked is not None
        assert revoked.reason == "admin_revoked"
        assert revoked.revoked_by == admin_user.id

    @patch("core.server.generate_crl", return_value=b"fake-crl")
    @patch("core.server.update_crl_file")
    def test_revoke_already_revoked(self, mock_update_crl, mock_gen_crl, client, app, admin_token):
        from core.auth import TokenAuth
        from models import User, db

        _auth = TokenAuth(secret_key="test")
        user = User(
            email="revoked@test.com",
            password_hash=_auth.hash_password("pass"),
            role="user",
            cert_serial_number=None,
            cert_revoked=True,
        )
        db.session.add(user)
        db.session.commit()

        resp = client.post(
            f"/api/v1/users/{user.id}/revoke-cert",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "NO_ACTIVE_CERT"

    def test_revoke_requires_admin(self, client, app, regular_user, user_token):
        resp = client.post(
            f"/api/v1/users/{regular_user.id}/revoke-cert",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403

    def test_revoke_user_not_found(self, client, app, admin_token):
        resp = client.post(
            "/api/v1/users/99999/revoke-cert",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404


class TestReissueCert:
    """Test POST /api/v1/users/<id>/reissue-cert."""

    @patch("core.server.generate_client_p12")
    def test_reissue_after_revoke(self, mock_p12, client, app, admin_token):
        from datetime import datetime

        from core.auth import TokenAuth
        from models import User, db

        mock_p12.return_value = (
            b"p12bytes",
            "randpass",
            999999,
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2027, 1, 1, tzinfo=UTC),
        )

        _auth = TokenAuth(secret_key="test")
        user = User(
            email="reissue@test.com",
            password_hash=_auth.hash_password("pass"),
            role="user",
            cert_serial_number=None,
            cert_revoked=True,
            is_approved=True,
        )
        db.session.add(user)
        db.session.commit()

        resp = client.post(
            f"/api/v1/users/{user.id}/reissue-cert",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["certRevoked"] is False

        # Verify DB state
        db_user = db.session.get(User, user.id)
        assert db_user.cert_revoked is False
        assert db_user.cert_serial_number == format(999999, "x")

    @patch("core.server.generate_client_p12")
    def test_reissue_with_active_cert_fails(self, mock_p12, client, app, admin_token):
        from core.auth import TokenAuth
        from models import User, db

        _auth = TokenAuth(secret_key="test")
        user = User(
            email="active@test.com",
            password_hash=_auth.hash_password("pass"),
            role="user",
            cert_serial_number="aaa",
            cert_revoked=False,
        )
        db.session.add(user)
        db.session.commit()

        resp = client.post(
            f"/api/v1/users/{user.id}/reissue-cert",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["code"] == "CERT_STILL_ACTIVE"


class TestCertStatus:
    """Test GET /api/v1/users/<id>/cert-status."""

    @patch("core.server.generate_crl", return_value=b"fake-crl")
    @patch("core.server.update_crl_file")
    def test_cert_status_with_history(self, mock_update_crl, mock_gen_crl, client, app, admin_user, admin_token):
        from core.auth import TokenAuth
        from models import RevokedCertificate, User, db

        _auth = TokenAuth(secret_key="test")
        user = User(
            email="status@test.com",
            password_hash=_auth.hash_password("pass"),
            role="user",
            cert_serial_number="beef01",
            cert_revoked=False,
            is_approved=True,
        )
        db.session.add(user)
        db.session.commit()

        # Add a historical revocation entry
        rc = RevokedCertificate(
            serial_number="oldserial",
            user_id=user.id,
            reason="admin_revoked",
            revoked_by=admin_user.id,
        )
        db.session.add(rc)
        db.session.commit()

        resp = client.get(
            f"/api/v1/users/{user.id}/cert-status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["serial"] == "beef01"
        assert data["isRevoked"] is False
        assert len(data["revocationHistory"]) == 1
        assert data["revocationHistory"][0]["serialNumber"] == "oldserial"
