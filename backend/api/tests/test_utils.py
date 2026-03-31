"""
Unit tests for server-level utility functions (get_file_list, user_has_access).
"""


class TestGetFileList:
    def test_nonexistent_path_returns_empty(self, app, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        result = srv.get_file_list("does/not/exist")
        assert result == []

    def test_lists_files_and_folders(self, app, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        (files_dir / "file.txt").write_text("content")
        (files_dir / "subdir").mkdir()

        result = srv.get_file_list()
        names = {item["name"] for item in result}
        assert "file.txt" in names
        assert "subdir" in names

    def test_hidden_files_excluded(self, app, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        (files_dir / ".hidden").write_text("secret")
        (files_dir / "visible.txt").write_text("hello")

        result = srv.get_file_list()
        names = [item["name"] for item in result]
        assert ".hidden" not in names
        assert "visible.txt" in names

    def test_mac_metadata_files_excluded(self, app, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        (files_dir / "._DSStore").write_text("meta")
        (files_dir / "real.txt").write_text("data")

        result = srv.get_file_list()
        names = [item["name"] for item in result]
        assert "._DSStore" not in names

    def test_folders_sorted_before_files(self, app, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        (files_dir / "z_file.txt").write_text("z")
        (files_dir / "a_dir").mkdir()

        result = srv.get_file_list()
        assert result[0]["type"] == "folder"

    def test_item_has_required_keys(self, app, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        (files_dir / "check.txt").write_text("hi")

        result = srv.get_file_list()
        assert len(result) == 1
        item = result[0]
        for key in ("id", "name", "path", "type", "size", "modifiedAt", "parentPath"):
            assert key in item

    def test_directory_traversal_blocked(self, app, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        (tmp_path / "files").mkdir()
        # Create a file outside the storage subdirectory
        (tmp_path / "secret.txt").write_text("should not be listed")

        result = srv.get_file_list("../../secret.txt")
        assert result == []


class TestResolveFilePath:
    def test_resolve_finds_file(self, app, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        files_dir = tmp_path / "files"
        files_dir.mkdir()
        (files_dir / "doc.txt").write_text("content")

        result = srv.resolve_file_path("doc.txt")
        assert result is not None
        assert result.name == "doc.txt"

    def test_resolve_returns_none_for_missing(self, app, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        (tmp_path / "files").mkdir()

        result = srv.resolve_file_path("nonexistent.txt")
        assert result is None

    def test_resolve_blocks_traversal(self, app, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        (tmp_path / "files").mkdir()
        (tmp_path / "outside.txt").write_text("should not be reachable")

        result = srv.resolve_file_path("../outside.txt")
        assert result is None


class TestUserHasAccess:
    def test_no_permissions_denies_all(self, app, regular_user):
        from core.server import user_has_access

        # No FolderPermission rows => no access (additive model)
        assert user_has_access(regular_user, "/any/path") is False

    def test_root_permission_covers_subpaths(self, app, regular_user):
        from core.server import user_has_access
        from models import FolderPermission, db

        # A permission on /docs covers /docs/sub paths
        perm = FolderPermission(user_id=regular_user.id, folder_path="/docs", can_read="allow", can_write="deny")
        db.session.add(perm)
        db.session.commit()

        assert user_has_access(regular_user, "/docs") is True
        assert user_has_access(regular_user, "/docs/sub") is True

    def test_specific_permission_overrides_parent(self, app, regular_user):
        from core.server import user_has_access
        from models import FolderPermission, db

        parent_perm = FolderPermission(
            user_id=regular_user.id, folder_path="/shared", can_read="allow", can_write="deny"
        )
        # More specific path overrides parent
        specific_perm = FolderPermission(
            user_id=regular_user.id, folder_path="/shared/secret", can_read="deny", can_write="deny"
        )
        db.session.add_all([parent_perm, specific_perm])
        db.session.commit()

        # /shared/secret is denied despite /shared being allowed
        assert user_has_access(regular_user, "/shared/secret") is False
        # /shared/public still allowed via /shared
        assert user_has_access(regular_user, "/shared/public") is True

    def test_write_permission_check(self, app, regular_user):
        from core.server import user_has_access
        from models import FolderPermission, db

        perm = FolderPermission(user_id=regular_user.id, folder_path="/uploads", can_read="allow", can_write="allow")
        db.session.add(perm)
        db.session.commit()

        assert user_has_access(regular_user, "/uploads", require_write=True) is True

    def test_no_write_permission_denied(self, app, regular_user):
        from core.server import user_has_access
        from models import FolderPermission, db

        perm = FolderPermission(user_id=regular_user.id, folder_path="/uploads", can_read="allow", can_write="deny")
        db.session.add(perm)
        db.session.commit()

        assert user_has_access(regular_user, "/uploads", require_write=True) is False

    def test_unmatched_path_denied(self, app, regular_user):
        from core.server import user_has_access
        from models import FolderPermission, db

        # Only /docs has a permission; /other has none
        perm = FolderPermission(user_id=regular_user.id, folder_path="/docs", can_read="allow", can_write="deny")
        db.session.add(perm)
        db.session.commit()

        assert user_has_access(regular_user, "/other") is False


class TestAdminEmailUsesHostname:
    def test_admin_email_uses_configured_hostname(self, app, monkeypatch):
        """Default admin user email should use the configured MDNS_HOSTNAME."""
        from core import server as srv
        from models import User

        monkeypatch.setitem(srv.CONFIG, "MDNS_HOSTNAME", "myraspberrypi")

        created = srv.create_default_admin("myraspberrypi", srv.CONFIG["ADMIN_PIN"])
        assert created is not None
        assert created.email == "admin@myraspberrypi.local"
        assert User.query.filter_by(email="admin@myraspberrypi.local").first() is not None

    def test_admin_email_reflects_different_hostnames(self, app, monkeypatch):
        """Admin email format should be admin@<hostname>.local for any configured hostname."""
        from core import server as srv
        from models import User, db

        for hostname in ("thumbsup", "pi-home", "mydevice"):
            # Clean up any admin created in a previous iteration
            User.query.filter_by(role="admin").delete()
            db.session.commit()

            created = srv.create_default_admin(hostname, srv.CONFIG["ADMIN_PIN"])
            assert created is not None
            assert created.email == f"admin@{hostname}.local"

    def test_create_default_admin_skips_if_admin_exists(self, app, admin_user):
        """create_default_admin should not create a second admin when one already exists."""
        from core import server as srv
        from models import User

        result = srv.create_default_admin("newhost", srv.CONFIG["ADMIN_PIN"])
        assert result is None
        assert User.query.filter_by(role="admin").count() == 1
