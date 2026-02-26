"""
Integration tests for core API endpoints (core/server.py).
"""

import io

# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


class TestLogin:
    def test_login_missing_body(self, client):
        r = client.post("/api/v1/auth/login", content_type="application/json")
        assert r.status_code == 400

    def test_login_missing_credentials(self, client):
        r = client.post("/api/v1/auth/login", json={"other": "field"})
        assert r.status_code == 400
        assert r.get_json()["code"] == "MISSING_CREDENTIALS"

    def test_login_invalid_credentials(self, client, app):
        r = client.post("/api/v1/auth/login", json={"email": "nobody@test.com", "password": "wrong"})
        assert r.status_code == 401

    def test_login_success(self, client, app, admin_user):
        r = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "adminpass"})
        assert r.status_code == 200
        data = r.get_json()
        assert "token" in data
        assert data["user"]["email"] == "admin@test.com"


class TestSignup:
    def test_signup_missing_body(self, client):
        r = client.post("/api/v1/auth/signup", content_type="application/json")
        assert r.status_code == 400

    def test_signup_invalid_email(self, client):
        r = client.post("/api/v1/auth/signup", json={"email": "notanemail", "password": "password123"})
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_EMAIL"

    def test_signup_short_password(self, client):
        r = client.post("/api/v1/auth/signup", json={"email": "new@test.com", "password": "abc"})
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_PASSWORD"

    def test_signup_success(self, client):
        r = client.post("/api/v1/auth/signup", json={"email": "new@test.com", "password": "securepass"})
        assert r.status_code == 201
        data = r.get_json()
        assert "token" in data
        assert data["user"]["email"] == "new@test.com"

    def test_signup_duplicate_email(self, client, admin_user):
        r = client.post("/api/v1/auth/signup", json={"email": "admin@test.com", "password": "anotherpass"})
        assert r.status_code == 409
        assert r.get_json()["code"] == "EMAIL_EXISTS"


class TestLogout:
    def test_logout_no_token(self, client):
        r = client.post("/api/v1/auth/logout")
        assert r.status_code == 401

    def test_logout_success(self, client, admin_token):
        r = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200


class TestGetCurrentUser:
    def test_me_no_token(self, client):
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401

    def test_me_with_valid_token(self, client, admin_token):
        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.get_json()
        assert data["user"]["email"] == "admin@test.com"


class TestRefreshToken:
    def test_refresh_no_token(self, client):
        r = client.post("/api/v1/auth/refresh")
        assert r.status_code == 401

    def test_refresh_success(self, client, admin_token):
        r = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert "token" in r.get_json()


class TestChangePassword:
    def test_change_password_no_token(self, client):
        r = client.post("/api/v1/auth/change-password", json={"newPassword": "newpass1"})
        assert r.status_code == 401

    def test_change_password_short_new_password(self, client, admin_token):
        r = client.post(
            "/api/v1/auth/change-password",
            json={"currentPassword": "adminpass", "newPassword": "ab"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_PASSWORD"

    def test_change_password_wrong_current(self, client, app, admin_token):
        r = client.post(
            "/api/v1/auth/change-password",
            json={"currentPassword": "wrongpass", "newPassword": "newvalidpass"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 401

    def test_change_password_success(self, client, app, admin_token):
        r = client.post(
            "/api/v1/auth/change-password",
            json={"currentPassword": "adminpass", "newPassword": "newvalidpass"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert "token" in r.get_json()


# ---------------------------------------------------------------------------
# Settings endpoints
# ---------------------------------------------------------------------------


class TestSettings:
    def test_get_settings(self, client):
        r = client.get("/api/v1/settings")
        assert r.status_code == 200
        data = r.get_json()
        assert "mode" in data

    def test_update_settings_no_auth(self, client):
        r = client.put("/api/v1/settings", json={"mode": "protected"})
        assert r.status_code in (401, 403)

    def test_update_settings_admin(self, client, admin_token):
        r = client.put(
            "/api/v1/settings",
            json={"mode": "protected"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.get_json()["mode"] == "protected"

    def test_update_settings_invalid_mode(self, client, admin_token):
        r = client.put(
            "/api/v1/settings",
            json={"mode": "invalid"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_MODE"


# ---------------------------------------------------------------------------
# User management endpoints
# ---------------------------------------------------------------------------


class TestUserManagement:
    def test_list_users_no_auth(self, client):
        r = client.get("/api/v1/users")
        assert r.status_code in (401, 403)

    def test_list_users_admin(self, client, admin_token):
        r = client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.get_json()
        assert "users" in data

    def test_create_user_admin(self, client, admin_token):
        r = client.post(
            "/api/v1/users",
            json={"email": "newuser@test.com", "password": "pass123", "role": "user"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201
        assert r.get_json()["user"]["email"] == "newuser@test.com"

    def test_create_user_invalid_role(self, client, admin_token):
        r = client.post(
            "/api/v1/users",
            json={"email": "u@test.com", "password": "pass123", "role": "superuser"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400
        assert r.get_json()["code"] == "INVALID_ROLE"

    def test_get_user_not_found(self, client, admin_token):
        r = client.get("/api/v1/users/9999", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 404

    def test_delete_self_forbidden(self, client, app, admin_user, admin_token):
        r = client.delete(
            f"/api/v1/users/{admin_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400
        assert r.get_json()["code"] == "CANNOT_DELETE_SELF"

    def test_delete_other_user(self, client, app, admin_token, regular_user):
        r = client.delete(
            f"/api/v1/users/{regular_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.get_json()["success"] is True


# ---------------------------------------------------------------------------
# File endpoints
# ---------------------------------------------------------------------------


class TestFileList:
    def test_list_files_open_mode(self, client, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        (tmp_path / "hello.txt").write_text("hi")

        r = client.get("/api/v1/files")
        assert r.status_code == 200
        data = r.get_json()
        assert "files" in data
        names = [f["name"] for f in data["files"]]
        assert "hello.txt" in names

    def test_list_files_search(self, client, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        (tmp_path / "report.pdf").write_text("content")
        (tmp_path / "image.png").write_text("content")

        r = client.get("/api/v1/files?search=report")
        assert r.status_code == 200
        data = r.get_json()
        assert len(data["files"]) == 1
        assert data["files"][0]["name"] == "report.pdf"


class TestFileUpload:
    def test_upload_no_file(self, client, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        monkeypatch.setitem(srv.CONFIG, "ENABLE_UPLOADS", True)

        r = client.post("/api/v1/files/upload", data={})
        assert r.status_code == 400
        assert r.get_json()["code"] == "NO_FILE"

    def test_upload_success(self, client, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        monkeypatch.setitem(srv.CONFIG, "ENABLE_UPLOADS", True)

        data = {"file": (io.BytesIO(b"hello world"), "test.txt")}
        r = client.post("/api/v1/files/upload", data=data, content_type="multipart/form-data")
        assert r.status_code == 201
        assert r.get_json()["file"]["name"] == "test.txt"

    def test_upload_disabled(self, client, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        monkeypatch.setitem(srv.CONFIG, "ENABLE_UPLOADS", False)

        data = {"file": (io.BytesIO(b"hello"), "blocked.txt")}
        r = client.post("/api/v1/files/upload", data=data, content_type="multipart/form-data")
        assert r.status_code == 403
        assert r.get_json()["code"] == "UPLOADS_DISABLED"


class TestFileDownload:
    def test_download_missing_path(self, client):
        r = client.get("/api/v1/files/download")
        assert r.status_code == 400

    def test_download_not_found(self, client, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        r = client.get("/api/v1/files/download?path=nonexistent.txt")
        assert r.status_code == 404

    def test_download_success(self, client, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        (tmp_path / "sample.txt").write_text("file content")

        r = client.get("/api/v1/files/download?path=sample.txt")
        assert r.status_code == 200


class TestMkdir:
    def test_mkdir_no_token(self, client, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        r = client.post("/api/v1/files/mkdir", json={"name": "newdir"})
        assert r.status_code == 401

    def test_mkdir_missing_name(self, client, admin_token, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        r = client.post(
            "/api/v1/files/mkdir",
            json={"name": ""},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 400
        assert r.get_json()["code"] == "MISSING_NAME"

    def test_mkdir_success(self, client, admin_token, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        r = client.post(
            "/api/v1/files/mkdir",
            json={"name": "mydir"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201
        assert r.get_json()["folder"]["name"] == "mydir"

    def test_mkdir_duplicate(self, client, admin_token, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        (tmp_path / "existing").mkdir()

        r = client.post(
            "/api/v1/files/mkdir",
            json={"name": "existing"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 409


class TestDeleteFile:
    def test_delete_disabled(self, client, admin_token, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        monkeypatch.setitem(srv.CONFIG, "ENABLE_DELETE", False)
        (tmp_path / "del.txt").write_text("x")

        r = client.delete(
            "/api/v1/files?path=del.txt",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 403
        assert r.get_json()["code"] == "DELETE_DISABLED"

    def test_delete_missing_path(self, client, admin_token, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        monkeypatch.setitem(srv.CONFIG, "ENABLE_DELETE", True)

        r = client.delete("/api/v1/files", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 400

    def test_delete_not_found(self, client, admin_token, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        monkeypatch.setitem(srv.CONFIG, "ENABLE_DELETE", True)

        r = client.delete(
            "/api/v1/files?path=ghost.txt",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    def test_delete_file_success(self, client, admin_token, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        monkeypatch.setitem(srv.CONFIG, "ENABLE_DELETE", True)
        (tmp_path / "todelete.txt").write_text("bye")

        r = client.delete(
            "/api/v1/files?path=todelete.txt",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.get_json()["success"] is True


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------


class TestDashboardStats:
    def test_dashboard_no_auth(self, client):
        r = client.get("/api/v1/stats/dashboard")
        assert r.status_code in (401, 403)

    def test_dashboard_admin(self, client, admin_token, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        r = client.get("/api/v1/stats/dashboard", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.get_json()
        assert "userCount" in data
        assert "fileCount" in data
