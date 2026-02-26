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
        (tmp_path / "file.txt").write_text("content")
        (tmp_path / "subdir").mkdir()

        result = srv.get_file_list()
        names = {item["name"] for item in result}
        assert "file.txt" in names
        assert "subdir" in names

    def test_hidden_files_excluded(self, app, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        (tmp_path / ".hidden").write_text("secret")
        (tmp_path / "visible.txt").write_text("hello")

        result = srv.get_file_list()
        names = [item["name"] for item in result]
        assert ".hidden" not in names
        assert "visible.txt" in names

    def test_mac_metadata_files_excluded(self, app, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        (tmp_path / "._DSStore").write_text("meta")
        (tmp_path / "real.txt").write_text("data")

        result = srv.get_file_list()
        names = [item["name"] for item in result]
        assert "._DSStore" not in names

    def test_folders_sorted_before_files(self, app, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        (tmp_path / "z_file.txt").write_text("z")
        (tmp_path / "a_dir").mkdir()

        result = srv.get_file_list()
        assert result[0]["type"] == "folder"

    def test_item_has_required_keys(self, app, monkeypatch, tmp_path):
        from core import server as srv

        monkeypatch.setitem(srv.CONFIG, "STORAGE_PATH", str(tmp_path))
        (tmp_path / "check.txt").write_text("hi")

        result = srv.get_file_list()
        assert len(result) == 1
        item = result[0]
        for key in ("id", "name", "path", "type", "size", "modifiedAt", "parentPath"):
            assert key in item


class TestUserHasAccess:
    def test_no_permissions_allows_all(self, app, regular_user):
        from core.server import user_has_access

        # No FolderPermission rows => default allow
        assert user_has_access(regular_user, "/any/path") is True

    def test_root_permission_covers_subpaths(self, app, regular_user):
        from core.server import user_has_access
        from models import FolderPermission, db

        # A permission on /docs covers /docs/sub paths
        perm = FolderPermission(user_id=regular_user.id, folder_path="/docs", can_read=True, can_write=False)
        db.session.add(perm)
        db.session.commit()

        assert user_has_access(regular_user, "/docs") is True
        assert user_has_access(regular_user, "/docs/sub") is True

    def test_specific_permission_overrides_parent(self, app, regular_user):
        from core.server import user_has_access
        from models import FolderPermission, db

        parent_perm = FolderPermission(user_id=regular_user.id, folder_path="/shared", can_read=True, can_write=False)
        # More specific path overrides parent
        specific_perm = FolderPermission(
            user_id=regular_user.id, folder_path="/shared/secret", can_read=False, can_write=False
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

        perm = FolderPermission(user_id=regular_user.id, folder_path="/uploads", can_read=True, can_write=True)
        db.session.add(perm)
        db.session.commit()

        assert user_has_access(regular_user, "/uploads", require_write=True) is True

    def test_no_write_permission_denied(self, app, regular_user):
        from core.server import user_has_access
        from models import FolderPermission, db

        perm = FolderPermission(user_id=regular_user.id, folder_path="/uploads", can_read=True, can_write=False)
        db.session.add(perm)
        db.session.commit()

        assert user_has_access(regular_user, "/uploads", require_write=True) is False

    def test_unmatched_path_denied(self, app, regular_user):
        from core.server import user_has_access
        from models import FolderPermission, db

        # Only /docs has a permission; /other has none
        perm = FolderPermission(user_id=regular_user.id, folder_path="/docs", can_read=True, can_write=False)
        db.session.add(perm)
        db.session.commit()

        assert user_has_access(regular_user, "/other") is False
