"""
Unit tests for database models (models.py).
"""

import pytest


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
        for key in ("id", "authMethod", "tlsEnabled", "httpsPort", "deviceName"):
            assert key in d

    def test_settings_repr(self, app):
        from models import SystemSettings

        settings = SystemSettings.query.first()
        r = repr(settings)
        assert "auth=" in r


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


class TestPathCertRuleModel:
    def test_path_cert_rule_to_dict(self, app):
        from models import PathCertRule, db

        rule = PathCertRule(dir_path="/secret", attr_name="O", attr_value="AcmeCorp")
        db.session.add(rule)
        db.session.commit()

        d = rule.to_dict()
        assert d["dirPath"] == "/secret"
        assert d["attrName"] == "O"
        assert d["attrValue"] == "AcmeCorp"
        assert "id" in d
        assert "createdAt" in d

    def test_path_cert_rule_repr(self, app):
        from models import PathCertRule, db

        rule = PathCertRule(dir_path="/docs", attr_name="OU", attr_value="Engineering")
        db.session.add(rule)
        db.session.commit()

        r = repr(rule)
        assert "/docs" in r
        assert "OU" in r
        assert "Engineering" in r

    def test_multiple_rules_for_same_path(self, app):
        from models import PathCertRule, db

        rules = [
            PathCertRule(dir_path="/restricted", attr_name="O", attr_value="AcmeCorp"),
            PathCertRule(dir_path="/restricted", attr_name="OU", attr_value="DevOps"),
            PathCertRule(dir_path="/restricted", attr_name="L", attr_value="Seattle"),
        ]
        db.session.add_all(rules)
        db.session.commit()

        stored = PathCertRule.query.filter_by(dir_path="/restricted").all()
        assert len(stored) == 3

    def test_or_logic_multiple_values_same_attr(self, app):
        """Multiple values for the same attr on the same dir_path = OR logic."""
        from models import PathCertRule, db

        rules = [
            PathCertRule(dir_path="/shared", attr_name="OU", attr_value="Engineering"),
            PathCertRule(dir_path="/shared", attr_name="OU", attr_value="Research"),
        ]
        db.session.add_all(rules)
        db.session.commit()

        stored = PathCertRule.query.filter_by(dir_path="/shared", attr_name="OU").all()
        values = {r.attr_value for r in stored}
        assert values == {"Engineering", "Research"}

    def test_unique_constraint_prevents_duplicates(self, app):
        from sqlalchemy.exc import IntegrityError

        from models import PathCertRule, db

        db.session.add(PathCertRule(dir_path="/locked", attr_name="C", attr_value="US"))
        db.session.commit()

        db.session.add(PathCertRule(dir_path="/locked", attr_name="C", attr_value="US"))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_different_paths_same_rule(self, app):
        from models import PathCertRule, db

        rules = [
            PathCertRule(dir_path="/alpha", attr_name="O", attr_value="MyOrg"),
            PathCertRule(dir_path="/beta", attr_name="O", attr_value="MyOrg"),
        ]
        db.session.add_all(rules)
        db.session.commit()

        assert PathCertRule.query.filter_by(dir_path="/alpha").count() == 1
        assert PathCertRule.query.filter_by(dir_path="/beta").count() == 1

    def test_attribute_agnostic_arbitrary_attr_name(self, app):
        """Arbitrary/custom attribute names should be stored without schema changes."""
        from models import PathCertRule, db

        # 1.2.840.113549.1.9.1 is the OID for the emailAddress DN attribute
        rule = PathCertRule(dir_path="/custom", attr_name="1.2.840.113549.1.9.1", attr_value="admin@example.com")
        db.session.add(rule)
        db.session.commit()

        stored = PathCertRule.query.filter_by(dir_path="/custom").first()
        assert stored.attr_name == "1.2.840.113549.1.9.1"
        assert stored.attr_value == "admin@example.com"
