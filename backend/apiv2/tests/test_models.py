"""
Unit tests for database models (models.py).
"""


class TestUserModel:
    def test_user_to_dict_keys(self, app, regular_user):
        d = regular_user.to_dict()
        for key in ("id", "email", "role", "requiresPasswordChange", "created_at", "last_login"):
            assert key in d

    def test_user_to_dict_no_password_hash(self, app, regular_user):
        d = regular_user.to_dict()
        assert "password_hash" not in d

    def test_user_to_dict_include_permissions(self, app, regular_user):
        d = regular_user.to_dict(include_permissions=True)
        assert "folderPermissions" in d
        assert isinstance(d["folderPermissions"], list)

    def test_user_repr(self, app, regular_user):
        r = repr(regular_user)
        assert "user@test.com" in r

    def test_admin_user_role(self, app, admin_user):
        assert admin_user.role == "admin"


class TestSystemSettingsModel:
    def test_settings_to_dict_keys(self, app):
        from models import SystemSettings

        settings = SystemSettings.query.first()
        d = settings.to_dict()
        for key in ("id", "mode", "authMethod", "tlsEnabled", "httpsPort", "deviceName"):
            assert key in d

    def test_settings_repr(self, app):
        from models import SystemSettings

        settings = SystemSettings.query.first()
        r = repr(settings)
        assert "mode=" in r


class TestFolderPermissionModel:
    def test_folder_permission_to_dict(self, app, regular_user):
        from models import FolderPermission, db

        perm = FolderPermission(
            user_id=regular_user.id,
            folder_path="/docs",
            can_read=True,
            can_write=False,
        )
        db.session.add(perm)
        db.session.commit()

        d = perm.to_dict()
        assert d["userId"] == regular_user.id
        assert d["path"] == "/docs"
        assert d["read"] is True
        assert d["write"] is False

    def test_folder_permission_repr(self, app, regular_user):
        from models import FolderPermission, db

        perm = FolderPermission(
            user_id=regular_user.id,
            folder_path="/photos",
            can_read=True,
            can_write=True,
        )
        db.session.add(perm)
        db.session.commit()

        r = repr(perm)
        assert "/photos" in r

    def test_cascade_delete_removes_permissions(self, app, regular_user):
        from models import FolderPermission, db

        perm = FolderPermission(
            user_id=regular_user.id,
            folder_path="/videos",
            can_read=True,
            can_write=False,
        )
        db.session.add(perm)
        db.session.commit()

        db.session.delete(regular_user)
        db.session.commit()

        remaining = FolderPermission.query.filter_by(folder_path="/videos").all()
        assert remaining == []
