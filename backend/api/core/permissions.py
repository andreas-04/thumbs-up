"""
Layered permission resolver for ThumbsUp.

Resolves effective permissions for a user by merging three tiers:
  1. Domain defaults  – from DomainConfig matching the user's email domain
  2. Group permissions – OR across all groups the user belongs to; group overrides domain
  3. User overrides   – FolderPermission rows; **tri-state** per flag:
       * ``"allow"``  – explicit grant  (overrides group/domain)
       * ``"deny"``   – explicit deny   (overrides group/domain)
       * ``None``     – no action; the group/domain value passes through

Within the same tier (multiple groups), most-permissive wins (OR).
Across tiers, more-granular replaces less-granular at the same path –
except user-level ``None`` defers to the lower tier.

Permissions are **additive** — by default users have **no access**.  Each tier
can only grant additional access.  Admin users bypass all checks.
"""

from models import DomainConfig, FolderPermission


def _normalise_path(path):
    """Normalise a folder path to start with '/' and have no trailing slash."""
    normalised = "/" + path.strip("/")
    if normalised != "/":
        normalised = normalised.rstrip("/")
    return normalised


def _user_flag_to_bool(value, fallback):
    """Convert a tri-state user flag to a concrete boolean.

    * ``"allow"`` → True
    * ``"deny"``  → False
    * ``None``    → *fallback* (from group/domain layer)
    """
    if value == "allow":
        return True
    if value == "deny":
        return False
    return fallback


def resolve_permissions(user):
    """Return the effective permission set for *user*.

    Returns:
        dict  – ``{path: {"can_read": bool, "can_write": bool, "source": str}}``
        where *source* is ``"domain"``, ``"group"`` or ``"user"``.

        An **empty** dict means no permissions were configured at any tier
        (the caller should treat this as full default access).
    """
    effective = {}

    # --- Tier 1: Domain defaults ---
    email_domain = user.email.rsplit("@", 1)[-1].lower() if "@" in user.email else ""
    if email_domain:
        domain_cfg = DomainConfig.query.filter_by(domain=email_domain).first()
        if domain_cfg:
            for dp in domain_cfg.permissions:
                p = _normalise_path(dp.folder_path)
                effective[p] = {
                    "can_read": dp.can_read,
                    "can_write": dp.can_write,
                    "source": "domain",
                }

    # --- Tier 2: Group permissions (OR across groups, then override domain) ---
    groups = user.groups  # eagerly loaded via relationship
    if groups:
        # Collect all group permissions, keyed by normalised path.
        # For each path, OR the flags across all groups (most permissive wins).
        group_merged = {}  # path -> {can_read, can_write}
        for grp in groups:
            for gp in grp.permissions:
                p = _normalise_path(gp.folder_path)
                if p in group_merged:
                    group_merged[p]["can_read"] = group_merged[p]["can_read"] or gp.can_read
                    group_merged[p]["can_write"] = group_merged[p]["can_write"] or gp.can_write
                else:
                    group_merged[p] = {"can_read": gp.can_read, "can_write": gp.can_write}

        # Group results override domain at the same path; additive for new paths.
        for p, flags in group_merged.items():
            effective[p] = {
                "can_read": flags["can_read"],
                "can_write": flags["can_write"],
                "source": "group",
            }

    # --- Tier 3: User overrides (tri-state: allow / deny / None) ---
    user_perms = FolderPermission.query.filter_by(user_id=user.id).all()
    for up in user_perms:
        p = _normalise_path(up.folder_path)

        # Get the current effective values at this path (from domain/group)
        # so that None (no action) can fall through.
        base = effective.get(p, {"can_read": False, "can_write": False, "source": "none"})

        read_val = _user_flag_to_bool(up.can_read, base["can_read"])
        write_val = _user_flag_to_bool(up.can_write, base["can_write"])

        # Determine the source label.  If both flags are None the user row
        # has no effect, so keep the original source.
        if up.can_read is not None or up.can_write is not None:
            source = "user"
        else:
            source = base["source"]

        effective[p] = {
            "can_read": read_val,
            "can_write": write_val,
            "source": source,
        }

    return effective


def resolve_permissions_detailed(user):
    """Return a per-path breakdown with source attribution for admin UI.

    Returns:
        dict – ``{path: { "domain": {...}|None, "groups": [...], "groupMerged": {...}|None,
                          "user": {...}|None, "effective": {...} }}``
    """
    all_paths = set()
    domain_map = {}
    groups_map = {}   # path -> list of {groupId, groupName, canRead, canWrite}
    group_merged_map = {}
    user_map = {}

    # --- Domain ---
    email_domain = user.email.rsplit("@", 1)[-1].lower() if "@" in user.email else ""
    if email_domain:
        domain_cfg = DomainConfig.query.filter_by(domain=email_domain).first()
        if domain_cfg:
            for dp in domain_cfg.permissions:
                p = _normalise_path(dp.folder_path)
                all_paths.add(p)
                domain_map[p] = {"canRead": dp.can_read, "canWrite": dp.can_write}

    # --- Groups ---
    for grp in user.groups:
        for gp in grp.permissions:
            p = _normalise_path(gp.folder_path)
            all_paths.add(p)
            groups_map.setdefault(p, []).append({
                "groupId": grp.id,
                "groupName": grp.name,
                "canRead": gp.can_read,
                "canWrite": gp.can_write,
            })

    # Merge across groups per path (OR)
    for p, grp_entries in groups_map.items():
        merged_read = any(g["canRead"] for g in grp_entries)
        merged_write = any(g["canWrite"] for g in grp_entries)
        group_merged_map[p] = {"canRead": merged_read, "canWrite": merged_write}

    # --- User ---
    user_perms = FolderPermission.query.filter_by(user_id=user.id).all()
    for up in user_perms:
        p = _normalise_path(up.folder_path)
        all_paths.add(p)
        user_map[p] = {"canRead": up.can_read, "canWrite": up.can_write}  # tri-state strings

    # --- Build detailed result ---
    result = {}
    for p in sorted(all_paths):
        # Effective: user > group > domain, with user tri-state fall-through
        if p in user_map:
            # Start from group or domain base, apply user overrides
            if p in group_merged_map:
                base_read = group_merged_map[p]["canRead"]
                base_write = group_merged_map[p]["canWrite"]
            elif p in domain_map:
                base_read = domain_map[p]["canRead"]
                base_write = domain_map[p]["canWrite"]
            else:
                base_read = False
                base_write = False

            eff_read = _user_flag_to_bool(user_map[p]["canRead"], base_read)
            eff_write = _user_flag_to_bool(user_map[p]["canWrite"], base_write)
            eff_source = "user" if (user_map[p]["canRead"] is not None or user_map[p]["canWrite"] is not None) else (
                "group" if p in group_merged_map else ("domain" if p in domain_map else "none")
            )
            eff = {"canRead": eff_read, "canWrite": eff_write, "source": eff_source}
        elif p in group_merged_map:
            eff = {"canRead": group_merged_map[p]["canRead"], "canWrite": group_merged_map[p]["canWrite"], "source": "group"}
        elif p in domain_map:
            eff = {"canRead": domain_map[p]["canRead"], "canWrite": domain_map[p]["canWrite"], "source": "domain"}
        else:
            eff = {"canRead": False, "canWrite": False, "source": "none"}

        result[p] = {
            "domain": domain_map.get(p),
            "groups": groups_map.get(p, []),
            "groupMerged": group_merged_map.get(p),
            "user": user_map.get(p),
            "effective": eff,
        }

    return result


def check_access(user, folder_path, require_write=False):
    """Check whether *user* can access *folder_path*.

    A permission on ``/docs`` grants access to ``/docs`` and all its children
    (e.g. ``/docs/sub``).  There is no root wildcard — ``/`` is not a valid
    permission path.

    Returns True if access is granted, False otherwise.
    Admins bypass this function (checked by caller).
    """
    effective = resolve_permissions(user)

    if not effective:
        return False

    normalised = _normalise_path(folder_path)

    # Longest-prefix match: find the most specific permission that covers
    # the requested path.
    best_path = None
    best_entry = None
    for perm_path, entry in effective.items():
        is_prefix = normalised == perm_path or normalised.startswith(perm_path + "/")
        if is_prefix:
            if best_path is None or len(perm_path) > len(best_path):
                best_path = perm_path
                best_entry = entry

    if best_entry is None:
        return False

    return best_entry["can_write"] if require_write else best_entry["can_read"]


def visible_paths(user):
    """Return the set of normalised paths the user has read access to.

    Used by the file listing endpoint to filter directory contents so that
    users only see folders they can access (or folders that lead toward
    granted areas).
    """
    effective = resolve_permissions(user)
    return {p for p, e in effective.items() if e["can_read"]}


def is_item_visible(item_path, item_is_folder, granted_paths):
    """Decide whether a single directory entry should be shown to the user.

    Args:
        item_path: Normalised path of the item (e.g. ``/docs``).
        item_is_folder: True if the item is a directory.
        granted_paths: Set of normalised paths where the user has read access
                       (from ``visible_paths``).

    Returns True if the item should be included in the listing.
    """
    for gp in granted_paths:
        # 1. Item is inside a granted folder → show it
        if item_path == gp or item_path.startswith(gp + "/"):
            return True
        # 2. Item is a folder on the *path toward* a granted folder → show it
        #    so the user can navigate there.
        if item_is_folder and gp.startswith(item_path + "/"):
            return True
    return False
