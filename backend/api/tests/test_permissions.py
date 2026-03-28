"""
Tests for the layered permission resolver and new API endpoints.
"""

import json


# ============================================================================
# Permission resolver unit tests
# ============================================================================

class TestResolvePermissions:
    """Tests for resolve_permissions()."""

    def test_no_permissions_returns_empty(self, app, regular_user):
        """User with no domain/group/user perms → empty dict (no access)."""
        from core.permissions import resolve_permissions

        result = resolve_permissions(regular_user)
        assert result == {}

    def test_domain_only(self, app, regular_user, domain_config):
        """User with only domain defaults → domain permissions apply."""
        from core.permissions import resolve_permissions

        result = resolve_permissions(regular_user)
        assert "/shared" in result
        assert result["/shared"]["can_read"] is True
        assert result["/shared"]["can_write"] is False
        assert result["/shared"]["source"] == "domain"

    def test_group_overrides_domain(self, app, regular_user, domain_config, group_with_perms):
        """Group permission replaces domain permission at the same path."""
        from core.permissions import resolve_permissions
        from models import GroupMembership, db

        # Add user to group
        db.session.add(GroupMembership(group_id=group_with_perms.id, user_id=regular_user.id))
        db.session.commit()

        result = resolve_permissions(regular_user)
        # /shared exists in both domain (r) and group (r/w) → group wins
        assert result["/shared"]["can_read"] is True
        assert result["/shared"]["can_write"] is True
        assert result["/shared"]["source"] == "group"

    def test_multi_group_most_permissive(self, app, regular_user):
        """Multiple groups: most permissive wins (OR) across groups."""
        from core.permissions import resolve_permissions
        from models import Group, GroupMembership, GroupPermission, db

        g1 = Group(name="g1")
        g2 = Group(name="g2")
        db.session.add_all([g1, g2])
        db.session.flush()

        # g1: /docs → r only; g2: /docs → w only
        db.session.add(GroupPermission(group_id=g1.id, folder_path="/docs", can_read=True, can_write=False))
        db.session.add(GroupPermission(group_id=g2.id, folder_path="/docs", can_read=False, can_write=True))
        db.session.add(GroupMembership(group_id=g1.id, user_id=regular_user.id))
        db.session.add(GroupMembership(group_id=g2.id, user_id=regular_user.id))
        db.session.commit()

        result = resolve_permissions(regular_user)
        assert result["/docs"]["can_read"] is True
        assert result["/docs"]["can_write"] is True
        assert result["/docs"]["source"] == "group"

    def test_user_overrides_group(self, app, regular_user, group_with_perms):
        """User-level permission replaces merged group result at the same path."""
        from core.permissions import resolve_permissions
        from models import FolderPermission, GroupMembership, db

        # Add user to group (group gives r/w on /shared)
        db.session.add(GroupMembership(group_id=group_with_perms.id, user_id=regular_user.id))
        # User override: /shared → deny write
        db.session.add(FolderPermission(user_id=regular_user.id, folder_path="/shared", can_read="allow", can_write="deny"))
        db.session.commit()

        result = resolve_permissions(regular_user)
        assert result["/shared"]["can_read"] is True
        assert result["/shared"]["can_write"] is False
        assert result["/shared"]["source"] == "user"

    def test_full_three_layer_stack(self, app, regular_user, domain_config, group_with_perms):
        """Full stack: domain + group + user override → correct resolution."""
        from core.permissions import resolve_permissions
        from models import FolderPermission, GroupMembership, db

        db.session.add(GroupMembership(group_id=group_with_perms.id, user_id=regular_user.id))
        # User override on /docs only (not on /shared)
        db.session.add(FolderPermission(user_id=regular_user.id, folder_path="/docs", can_read="allow", can_write="deny"))
        db.session.commit()

        result = resolve_permissions(regular_user)
        # /shared → group wins over domain (group has r/w, domain has r)
        assert result["/shared"]["source"] == "group"
        assert result["/shared"]["can_write"] is True
        # /docs → user wins
        assert result["/docs"]["source"] == "user"
        assert result["/docs"]["can_write"] is False

    def test_additive_paths_across_tiers(self, app, regular_user, domain_config):
        """Paths from different tiers that don't conflict are all present."""
        from core.permissions import resolve_permissions
        from models import FolderPermission, db

        # Domain has /shared (from fixture), user has /private
        db.session.add(FolderPermission(user_id=regular_user.id, folder_path="/private", can_read="allow", can_write="allow"))
        db.session.commit()

        result = resolve_permissions(regular_user)
        assert "/shared" in result
        assert "/private" in result
        assert result["/shared"]["source"] == "domain"
        assert result["/private"]["source"] == "user"


class TestCheckAccess:
    """Tests for check_access() – longest-prefix matching on effective permissions."""

    def test_no_perms_denies_everything(self, app, regular_user):
        """Empty permission set → no access (additive model)."""
        from core.permissions import check_access

        assert check_access(regular_user, "/anything") is False
        assert check_access(regular_user, "/anything", require_write=True) is False

    def test_read_allowed_write_denied(self, app, regular_user):
        """User with allow-read / deny-write on /shared → can read, cannot write."""
        from core.permissions import check_access
        from models import FolderPermission, db

        db.session.add(FolderPermission(user_id=regular_user.id, folder_path="/shared", can_read="allow", can_write="deny"))
        db.session.commit()

        assert check_access(regular_user, "/shared/docs") is True
        assert check_access(regular_user, "/shared/docs", require_write=True) is False

    def test_longest_prefix_match(self, app, regular_user):
        """More specific path permission wins over broader one."""
        from core.permissions import check_access
        from models import FolderPermission, db

        db.session.add(FolderPermission(user_id=regular_user.id, folder_path="/shared", can_read="allow", can_write="deny"))
        db.session.add(FolderPermission(user_id=regular_user.id, folder_path="/shared/uploads", can_read="allow", can_write="allow"))
        db.session.commit()

        # /shared/docs inherits from /shared → no write
        assert check_access(regular_user, "/shared/docs", require_write=True) is False
        # /shared/uploads/sub inherits from /shared/uploads → write allowed
        assert check_access(regular_user, "/shared/uploads/sub", require_write=True) is True

    def test_uncovered_path_denied(self, app, regular_user):
        """Path not covered by any permission and not an ancestor → denied."""
        from core.permissions import check_access
        from models import FolderPermission, db

        db.session.add(FolderPermission(user_id=regular_user.id, folder_path="/docs", can_read="allow", can_write="deny"))
        db.session.commit()

        assert check_access(regular_user, "/other") is False

    def test_item_visibility_filtering(self, app, regular_user):
        """is_item_visible shows granted folders plus navigation ancestors."""
        from core.permissions import is_item_visible
        from models import FolderPermission, db

        # Only /docs/projects is granted
        db.session.add(FolderPermission(user_id=regular_user.id, folder_path="/docs/projects", can_read="allow", can_write="allow"))
        db.session.commit()

        granted = {"/docs/projects"}

        # /docs is a folder leading toward a granted area → visible
        assert is_item_visible("/docs", True, granted) is True
        # /docs/projects itself → visible (exact match)
        assert is_item_visible("/docs/projects", True, granted) is True
        # /docs/projects/sub → visible (inside granted folder)
        assert is_item_visible("/docs/projects/sub", True, granted) is True
        # A file inside the granted folder → visible
        assert is_item_visible("/docs/projects/readme.txt", False, granted) is True
        # Sibling folder → not visible
        assert is_item_visible("/other", True, granted) is False
        # Sibling inside /docs → not visible
        assert is_item_visible("/docs/private", True, granted) is False
        # A file inside /docs (outside /docs/projects) → not visible
        assert is_item_visible("/docs/readme.txt", False, granted) is False

    def test_domain_permissions_used(self, app, regular_user, domain_config):
        """Domain perms are picked up by check_access."""
        from core.permissions import check_access

        # domain_config fixture gives /shared → read only for test.com
        assert check_access(regular_user, "/shared/sub/path") is True
        assert check_access(regular_user, "/shared/sub/path", require_write=True) is False
        # Path outside /shared is denied
        assert check_access(regular_user, "/other") is False

    def test_user_none_defers_to_group(self, app, regular_user, group_with_perms):
        """User tri-state None defers to group permission instead of overriding."""
        from core.permissions import check_access, resolve_permissions
        from models import FolderPermission, GroupMembership, db

        # Group gives r/w on /shared
        db.session.add(GroupMembership(group_id=group_with_perms.id, user_id=regular_user.id))
        # User: deny read, but leave write as None (should inherit group's True)
        db.session.add(FolderPermission(user_id=regular_user.id, folder_path="/shared", can_read="deny", can_write=None))
        db.session.commit()

        result = resolve_permissions(regular_user)
        assert result["/shared"]["can_read"] is False   # explicit deny
        assert result["/shared"]["can_write"] is True    # inherited from group

    def test_user_all_none_keeps_base_source(self, app, regular_user, domain_config):
        """User row with both flags None preserves base tier's source label."""
        from core.permissions import resolve_permissions
        from models import FolderPermission, db

        # Domain gives /shared (from fixture); user row has no action on both
        db.session.add(FolderPermission(user_id=regular_user.id, folder_path="/shared", can_read=None, can_write=None))
        db.session.commit()

        result = resolve_permissions(regular_user)
        assert result["/shared"]["source"] == "domain"
        assert result["/shared"]["can_read"] is True
class TestResolvePermissionsDetailed:
    """Tests for resolve_permissions_detailed()."""

    def test_shows_all_sources(self, app, regular_user, domain_config, group_with_perms):
        """Detailed view includes domain, group, and user sources."""
        from core.permissions import resolve_permissions_detailed
        from models import FolderPermission, GroupMembership, db

        db.session.add(GroupMembership(group_id=group_with_perms.id, user_id=regular_user.id))
        db.session.add(FolderPermission(user_id=regular_user.id, folder_path="/shared", can_read="deny", can_write="deny"))
        db.session.commit()

        result = resolve_permissions_detailed(regular_user)
        entry = result["/shared"]
        assert entry["domain"] is not None
        assert len(entry["groups"]) > 0
        assert entry["user"] is not None
        # User override wins
        assert entry["effective"]["source"] == "user"
        assert entry["effective"]["canRead"] is False


# ============================================================================
# API endpoint integration tests
# ============================================================================


class TestDomainAPI:
    """Tests for /api/v1/domains endpoints."""

    def test_crud_lifecycle(self, client, admin_token):
        """Create, read, update, delete a domain config."""
        h = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

        # Create
        resp = client.post("/api/v1/domains", headers=h, data=json.dumps({
            "domain": "example.com",
            "permissions": [{"path": "/shared", "read": True, "write": False}],
        }))
        assert resp.status_code == 201
        domain_id = resp.get_json()["domain"]["id"]

        # List
        resp = client.get("/api/v1/domains", headers=h)
        assert resp.status_code == 200
        assert len(resp.get_json()["domains"]) >= 1

        # Get
        resp = client.get(f"/api/v1/domains/{domain_id}", headers=h)
        assert resp.status_code == 200
        assert resp.get_json()["domain"]["domain"] == "example.com"

        # Update
        resp = client.put(f"/api/v1/domains/{domain_id}", headers=h, data=json.dumps({
            "domain": "newexample.com",
            "permissions": [{"path": "/shared", "read": True, "write": True}],
        }))
        assert resp.status_code == 200
        assert resp.get_json()["domain"]["domain"] == "newexample.com"

        # Delete
        resp = client.delete(f"/api/v1/domains/{domain_id}", headers=h)
        assert resp.status_code == 200

    def test_duplicate_domain_rejected(self, client, admin_token):
        h = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        client.post("/api/v1/domains", headers=h, data=json.dumps({"domain": "dup.com"}))
        resp = client.post("/api/v1/domains", headers=h, data=json.dumps({"domain": "dup.com"}))
        assert resp.status_code == 409

    def test_requires_admin(self, client, user_token):
        h = {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}
        resp = client.get("/api/v1/domains", headers=h)
        assert resp.status_code == 403


class TestGroupAPI:
    """Tests for /api/v1/groups endpoints."""

    def test_crud_lifecycle(self, client, admin_token, regular_user):
        """Create, read, update, delete a group + manage members/permissions."""
        h = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

        # Create
        resp = client.post("/api/v1/groups", headers=h, data=json.dumps({
            "name": "Engineers",
            "description": "Engineering team",
        }))
        assert resp.status_code == 201
        group_id = resp.get_json()["group"]["id"]

        # List
        resp = client.get("/api/v1/groups", headers=h)
        assert resp.status_code == 200

        # Get (with members)
        resp = client.get(f"/api/v1/groups/{group_id}", headers=h)
        assert resp.status_code == 200
        assert resp.get_json()["group"]["name"] == "Engineers"

        # Update permissions
        resp = client.put(f"/api/v1/groups/{group_id}/permissions", headers=h, data=json.dumps({
            "permissions": [{"path": "/shared", "read": True, "write": True}],
        }))
        assert resp.status_code == 200
        assert len(resp.get_json()["permissions"]) == 1

        # Update members
        resp = client.put(f"/api/v1/groups/{group_id}/members", headers=h, data=json.dumps({
            "userIds": [regular_user.id],
        }))
        assert resp.status_code == 200
        assert len(resp.get_json()["group"]["members"]) == 1

        # Update metadata
        resp = client.put(f"/api/v1/groups/{group_id}", headers=h, data=json.dumps({
            "name": "Eng",
        }))
        assert resp.status_code == 200
        assert resp.get_json()["group"]["name"] == "Eng"

        # Delete
        resp = client.delete(f"/api/v1/groups/{group_id}", headers=h)
        assert resp.status_code == 200

    def test_duplicate_group_rejected(self, client, admin_token):
        h = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        client.post("/api/v1/groups", headers=h, data=json.dumps({"name": "dup"}))
        resp = client.post("/api/v1/groups", headers=h, data=json.dumps({"name": "dup"}))
        assert resp.status_code == 409


class TestEffectivePermissionsAPI:
    """Tests for /api/v1/users/<id>/effective-permissions."""

    def test_returns_detailed_breakdown(self, client, admin_token, regular_user, domain_config, group_with_perms):
        from models import GroupMembership, db

        db.session.add(GroupMembership(group_id=group_with_perms.id, user_id=regular_user.id))
        db.session.commit()

        h = {"Authorization": f"Bearer {admin_token}"}
        resp = client.get(f"/api/v1/users/{regular_user.id}/effective-permissions", headers=h)
        assert resp.status_code == 200
        perms = resp.get_json()["permissions"]
        assert "/shared" in perms
        assert "effective" in perms["/shared"]

    def test_empty_for_user_with_no_perms(self, client, admin_token, regular_user):
        h = {"Authorization": f"Bearer {admin_token}"}
        resp = client.get(f"/api/v1/users/{regular_user.id}/effective-permissions", headers=h)
        assert resp.status_code == 200
        assert resp.get_json()["permissions"] == {}


class TestUserGroupAssignment:
    """Tests for /api/v1/users/<id>/groups."""

    def test_assign_and_verify(self, client, admin_token, regular_user, group_with_perms):
        h = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        resp = client.put(f"/api/v1/users/{regular_user.id}/groups", headers=h, data=json.dumps({
            "groupIds": [group_with_perms.id],
        }))
        assert resp.status_code == 200
        user_data = resp.get_json()["user"]
        assert len(user_data["groups"]) == 1
        assert user_data["groups"][0]["id"] == group_with_perms.id
