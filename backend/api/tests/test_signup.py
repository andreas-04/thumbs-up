"""
Tests for the signup endpoint with domain allowlist logic.
"""


class TestSignupDomainAllowlist:
    """Test POST /api/v1/auth/signup with domain allowlist checks."""

    def test_signup_allowed_domain_succeeds(self, client, app):
        """Signup with an allowlisted domain creates an approved user."""
        from models import SystemSettings, db

        settings = SystemSettings.query.first()
        settings.allowed_domains = "mycorp.com"
        db.session.commit()

        resp = client.post(
            "/api/v1/auth/signup",
            json={"email": "alice@mycorp.com", "password": "securepass123"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["user"]["isApproved"] is True
        assert "token" in data

    def test_signup_disallowed_domain_rejected(self, client, app):
        """Signup with a non-allowlisted domain returns 403."""
        from models import SystemSettings, db

        settings = SystemSettings.query.first()
        settings.allowed_domains = "mycorp.com"
        db.session.commit()

        resp = client.post(
            "/api/v1/auth/signup",
            json={"email": "bob@random.com", "password": "securepass123"},
        )
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["code"] == "DOMAIN_NOT_ALLOWED"

    def test_signup_no_allowed_domains_rejected(self, client, app):
        """Signup when no domains are configured returns 403."""
        resp = client.post(
            "/api/v1/auth/signup",
            json={"email": "eve@anything.com", "password": "securepass123"},
        )
        assert resp.status_code == 403

    def test_signup_claim_precreated_account(self, client, app):
        """Claiming a pre-approved admin-created account still works."""
        from core.auth import TokenAuth
        from models import User, db

        _auth = TokenAuth()
        pre_user = User(
            email="invited@company.com",
            password_hash=_auth.hash_password("temp-cert-password"),
            role="user",
            is_default_pin=True,
            is_approved=True,
        )
        db.session.add(pre_user)
        db.session.commit()

        resp = client.post(
            "/api/v1/auth/signup",
            json={"email": "invited@company.com", "password": "mynewpassword"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["user"]["isApproved"] is True

    def test_signup_multiple_allowed_domains(self, client, app):
        """Multiple domains can be allowlisted."""
        from models import SystemSettings, db

        settings = SystemSettings.query.first()
        settings.allowed_domains = "alpha.com,beta.org,gamma.net"
        db.session.commit()

        resp = client.post(
            "/api/v1/auth/signup",
            json={"email": "user@beta.org", "password": "securepass123"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["user"]["isApproved"] is True


class TestSettingsAllowedDomains:
    """Test PUT /api/v1/settings with allowedDomains."""

    def _auth_header(self, token):
        """Build Authorization header, handling both str and bytes tokens."""
        t = token.decode() if isinstance(token, bytes) else token
        return {"Authorization": f"Bearer {t}"}

    def test_update_allowed_domains(self, client, admin_token):
        """Admin can set allowed domains via settings endpoint."""
        resp = client.put(
            "/api/v1/settings",
            json={"allowedDomains": ["mycorp.com", "partner.org"]},
            headers=self._auth_header(admin_token),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["allowedDomains"] == ["mycorp.com", "partner.org"]

    def test_update_allowed_domains_strips_at(self, client, admin_token):
        """Leading @ is stripped from domain entries."""
        resp = client.put(
            "/api/v1/settings",
            json={"allowedDomains": ["@example.com"]},
            headers=self._auth_header(admin_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["allowedDomains"] == ["example.com"]

    def test_update_allowed_domains_invalid(self, client, admin_token):
        """Invalid domains are rejected."""
        resp = client.put(
            "/api/v1/settings",
            json={"allowedDomains": ["nodot"]},
            headers=self._auth_header(admin_token),
        )
        assert resp.status_code == 400

    def test_get_settings_includes_allowed_domains(self, client, app):
        """GET /api/v1/settings returns allowedDomains."""
        resp = client.get("/api/v1/settings")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "allowedDomains" in data
        assert isinstance(data["allowedDomains"], list)
