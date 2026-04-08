"""
Database models for ThumbsUp authentication system.
"""

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="user")  # 'admin' or 'user'
    is_default_pin = db.Column(db.Boolean, default=False)  # True if using initial PIN
    is_approved = db.Column(db.Boolean, default=False)  # True if admin-approved for protected files
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Certificate tracking fields
    cert_serial_number = db.Column(db.String(255), nullable=True)  # Hex serial of current cert
    cert_revoked = db.Column(db.Boolean, default=False)  # True if current cert is revoked
    cert_issued_at = db.Column(db.DateTime, nullable=True)
    cert_expires_at = db.Column(db.DateTime, nullable=True)

    # Many-to-many relationship with Group via GroupMembership
    groups = db.relationship(
        "Group",
        secondary="group_memberships",
        back_populates="members",
        lazy=True,
    )

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"

    def to_dict(self, include_permissions=False):
        """Convert user to dictionary (without password_hash)."""
        result = {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "requiresPasswordChange": self.is_default_pin,  # Frontend-friendly name
            "isApproved": self.is_approved,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "groups": [{"id": g.id, "name": g.name} for g in self.groups],
            "certRevoked": self.cert_revoked,
            "certIssuedAt": self.cert_issued_at.isoformat() if self.cert_issued_at else None,
            "certExpiresAt": self.cert_expires_at.isoformat() if self.cert_expires_at else None,
        }
        if include_permissions:
            result["folderPermissions"] = [p.to_dict() for p in self.folder_permissions]
        return result


class SystemSettings(db.Model):
    """System settings model for application configuration."""

    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True)
    mode = db.Column(db.String(50), nullable=False, default="open")  # 'open' or 'protected'
    auth_method = db.Column(
        db.String(50), nullable=False, default="email+password"
    )  # 'email', 'email+password', 'username+password'
    tls_enabled = db.Column(db.Boolean, default=True)
    https_port = db.Column(db.Integer, default=8443)
    device_name = db.Column(db.String(255), default="ThumbsUp File Share")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # SMTP email notification settings
    smtp_enabled = db.Column(db.Boolean, default=False)
    smtp_host = db.Column(db.String(255), default="")
    smtp_port = db.Column(db.Integer, default=587)
    smtp_username = db.Column(db.String(255), default="")
    smtp_password = db.Column(db.String(255), default="")
    smtp_from_email = db.Column(db.String(255), default="")
    smtp_use_tls = db.Column(db.Boolean, default=True)

    # Domain allowlist for auto-approving signups (comma-separated domains)
    allowed_domains = db.Column(db.Text, default="")

    def __repr__(self):
        return f"<SystemSettings auth={self.auth_method}>"

    def to_dict(self):
        """Convert settings to dictionary."""
        return {
            "id": self.id,
            "authMethod": self.auth_method,
            "tlsEnabled": self.tls_enabled,
            "httpsPort": self.https_port,
            "deviceName": self.device_name,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "smtpEnabled": self.smtp_enabled or False,
            "smtpHost": self.smtp_host or "",
            "smtpPort": self.smtp_port or 587,
            "smtpUsername": self.smtp_username or "",
            "smtpPassword": "*****" if self.smtp_password else "",
            "smtpFromEmail": self.smtp_from_email or "",
            "smtpUseTls": self.smtp_use_tls if self.smtp_use_tls is not None else True,
            "allowedDomains": [d.strip() for d in (self.allowed_domains or "").split(",") if d.strip()],
        }


class FolderPermission(db.Model):
    """Folder permissions model for user-level ACLs.

    ``can_read`` and ``can_write`` are tri-state:
      * ``"allow"``  – explicit grant (overrides group/domain)
      * ``"deny"``   – explicit deny  (overrides group/domain)
      * ``None``      – no action; defers to group/domain permissions
    """

    __tablename__ = "folder_permissions"

    VALID_STATES = {"allow", "deny", None}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    folder_path = db.Column(db.String(1024), nullable=False)
    can_read = db.Column(db.String(5), nullable=True, default=None)  # "allow", "deny", or None
    can_write = db.Column(db.String(5), nullable=True, default=None)  # "allow", "deny", or None
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship("User", backref=db.backref("folder_permissions", lazy=True, cascade="all, delete-orphan"))

    # Unique constraint: one permission entry per user per folder
    __table_args__ = (db.UniqueConstraint("user_id", "folder_path", name="unique_user_folder"),)

    def __repr__(self):
        return f"<FolderPermission user_id={self.user_id} path={self.folder_path} r={self.can_read} w={self.can_write}>"

    def to_dict(self):
        """Convert permission to dictionary."""
        return {
            "id": self.id,
            "userId": self.user_id,
            "path": self.folder_path,
            "read": self.can_read,  # "allow", "deny", or null
            "write": self.can_write,  # "allow", "deny", or null
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class DomainConfig(db.Model):
    """Domain-level default permissions for all users from a given email domain."""

    __tablename__ = "domain_configs"

    id = db.Column(db.Integer, primary_key=True)
    domain = db.Column(db.String(255), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    permissions = db.relationship(
        "DomainPermission",
        backref=db.backref("domain_config", lazy=True),
        lazy=True,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<DomainConfig {self.domain}>"

    def to_dict(self):
        return {
            "id": self.id,
            "domain": self.domain,
            "permissions": [p.to_dict() for p in self.permissions],
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class DomainPermission(db.Model):
    """Path-based permission entry for a domain config."""

    __tablename__ = "domain_permissions"

    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey("domain_configs.id", ondelete="CASCADE"), nullable=False)
    folder_path = db.Column(db.String(1024), nullable=False)
    can_read = db.Column(db.Boolean, default=False)
    can_write = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("domain_id", "folder_path", name="unique_domain_folder"),)

    def __repr__(self):
        return f"<DomainPermission domain_id={self.domain_id} path={self.folder_path} r={self.can_read} w={self.can_write}>"

    def to_dict(self):
        return {
            "id": self.id,
            "domainId": self.domain_id,
            "path": self.folder_path,
            "read": self.can_read,
            "write": self.can_write,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class Group(db.Model):
    """Permission group with member users."""

    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.String(1024), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    permissions = db.relationship(
        "GroupPermission",
        backref=db.backref("group", lazy=True),
        lazy=True,
        cascade="all, delete-orphan",
    )
    members = db.relationship(
        "User",
        secondary="group_memberships",
        back_populates="groups",
        lazy=True,
    )

    def __repr__(self):
        return f"<Group {self.name}>"

    def to_dict(self, include_members=False):
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "memberCount": len(self.members),
            "permissionCount": len(self.permissions),
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_members:
            result["members"] = [{"id": u.id, "email": u.email} for u in self.members]
            result["permissions"] = [p.to_dict() for p in self.permissions]
        return result


class GroupPermission(db.Model):
    """Path-based permission entry for a group."""

    __tablename__ = "group_permissions"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    folder_path = db.Column(db.String(1024), nullable=False)
    can_read = db.Column(db.Boolean, default=False)
    can_write = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("group_id", "folder_path", name="unique_group_folder"),)

    def __repr__(self):
        return (
            f"<GroupPermission group_id={self.group_id} path={self.folder_path} r={self.can_read} w={self.can_write}>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "groupId": self.group_id,
            "path": self.folder_path,
            "read": self.can_read,
            "write": self.can_write,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class GroupMembership(db.Model):
    """Association table linking users to groups."""

    __tablename__ = "group_memberships"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("group_id", "user_id", name="unique_group_user"),)

    def __repr__(self):
        return f"<GroupMembership group_id={self.group_id} user_id={self.user_id}>"


class RevokedCertificate(db.Model):
    """Record of a revoked client certificate."""

    __tablename__ = "revoked_certificates"

    REASONS = {"admin_revoked", "expiry_approaching", "cn_mismatch_abuse", "reissued"}

    id = db.Column(db.Integer, primary_key=True)
    serial_number = db.Column(db.String(255), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    revoked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reason = db.Column(db.String(50), nullable=False)
    revoked_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    user = db.relationship("User", foreign_keys=[user_id], backref=db.backref("revoked_certs", lazy=True))

    def __repr__(self):
        return f"<RevokedCertificate serial={self.serial_number} reason={self.reason}>"

    def to_dict(self):
        return {
            "id": self.id,
            "serialNumber": self.serial_number,
            "userId": self.user_id,
            "revokedAt": self.revoked_at.isoformat() if self.revoked_at else None,
            "reason": self.reason,
            "revokedBy": self.revoked_by,
        }


class MtlsMismatchLog(db.Model):
    """Log of client certificate CN mismatches for abuse detection."""

    __tablename__ = "mtls_mismatch_logs"

    id = db.Column(db.Integer, primary_key=True)
    presented_cn = db.Column(db.String(255), nullable=False, index=True)
    authenticated_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<MtlsMismatchLog cn={self.presented_cn} user_id={self.authenticated_user_id}>"


class AuditLog(db.Model):
    """Append-only audit log of all system actions."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_email = db.Column(db.String(255), nullable=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.String(255), nullable=True)
    description = db.Column(db.String(1024), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    status = db.Column(db.String(10), nullable=False, default="success")
    metadata_json = db.Column(db.Text, nullable=True)

    __table_args__ = (db.Index("ix_audit_timestamp_action", "timestamp", "action"),)

    def __repr__(self):
        return f"<AuditLog {self.action} by {self.user_email} at {self.timestamp}>"

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "userId": self.user_id,
            "userEmail": self.user_email,
            "action": self.action,
            "targetType": self.target_type,
            "targetId": self.target_id,
            "description": self.description,
            "ipAddress": self.ip_address,
            "status": self.status,
        }
