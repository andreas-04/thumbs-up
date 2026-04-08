#!/usr/bin/env python3
"""
TerraCrate API v2 - Main Server
Ad-hoc file sharing server with web interface.
"""

import os
import socket
import ssl
import sys
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, send_file
from flask_cors import CORS
from werkzeug.serving import run_simple
from werkzeug.utils import secure_filename

# Local imports
from core.auth import TokenAuth
from core.permissions import check_access, resolve_permissions_detailed
from models import (
    AuditLog,
    DomainConfig,
    DomainPermission,
    Group,
    GroupMembership,
    GroupPermission,
    MtlsMismatchLog,
    RevokedCertificate,
    User,
    db,
)
from utils.audit import log_audit
from utils.email_sender import send_approval_email, send_invite_email, send_revocation_email
from utils.generate_certs import generate_client_p12, generate_crl, update_crl_file
from utils.mdns_advertiser import MDNSAdvertiser
from utils.qr_generator import QRGenerator

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Configuration
CONFIG = {
    "HOST": os.getenv("HOST", "0.0.0.0"),
    "PORT": int(os.getenv("PORT", 8443)),  # HTTPS port
    "STORAGE_PATH": os.getenv("STORAGE_PATH", str(BASE_DIR / "storage")),  # Absolute path
    "GUEST_STORAGE_PATH": os.getenv("GUEST_STORAGE_PATH", str(BASE_DIR / "guest-storage")),  # Guest files
    "CERT_PATH": os.getenv("CERT_PATH", str(BASE_DIR / "certs" / "server_cert.pem")),
    "KEY_PATH": os.getenv("KEY_PATH", str(BASE_DIR / "certs" / "server_key.pem")),
    "TOKEN_EXPIRY_HOURS": int(os.getenv("TOKEN_EXPIRY_HOURS", 24)),
    "ENABLE_UPLOADS": os.getenv("ENABLE_UPLOADS", "true").lower() == "true",
    "ENABLE_DELETE": os.getenv("ENABLE_DELETE", "true").lower() == "true",
    "SERVICE_NAME": os.getenv("SERVICE_NAME", "TerraCrate File Share"),
    "MDNS_HOSTNAME": os.getenv("MDNS_HOSTNAME", socket.gethostname()),
    "MAX_UPLOAD_SIZE": int(os.getenv("MAX_UPLOAD_SIZE", 100 * 1024 * 1024)),  # 100MB
    "ADMIN_PIN": os.getenv("ADMIN_PIN"),  # Must be set via environment
    "DATABASE_URI": os.getenv("DATABASE_URI", f"sqlite:///{BASE_DIR}/data/terracrate.db"),
    "CORS_ORIGINS": os.getenv("CORS_ORIGINS", "*"),  # Comma-separated origins or '*'
}

# Initialize Flask app with explicit template folder
app = Flask(__name__, template_folder=str(TEMPLATE_DIR), static_folder=str(STATIC_DIR) if STATIC_DIR.exists() else None)
app.config["MAX_CONTENT_LENGTH"] = CONFIG["MAX_UPLOAD_SIZE"]
app.config["SQLALCHEMY_DATABASE_URI"] = CONFIG["DATABASE_URI"]
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Configure CORS
cors_origins = CONFIG["CORS_ORIGINS"]
if cors_origins == "*":
    CORS(app)
else:
    origins = [origin.strip() for origin in cors_origins.split(",")]
    CORS(app, origins=origins)

# Initialize database
db.init_app(app)

# Validate ADMIN_PIN is set
if not CONFIG["ADMIN_PIN"]:
    print("ERROR: ADMIN_PIN environment variable is not set!")
    print("   Please run startup.py which will configure the PIN.")
    sys.exit(1)

# Initialize auth with admin PIN
auth = TokenAuth(token_expiry_hours=CONFIG["TOKEN_EXPIRY_HOURS"], admin_pin=CONFIG["ADMIN_PIN"])

# Ensure storage directory exists
os.makedirs(CONFIG["STORAGE_PATH"], exist_ok=True)

# Ensure guest storage directory exists
os.makedirs(CONFIG["GUEST_STORAGE_PATH"], exist_ok=True)


def get_server_url():
    """Get the server's access URL."""
    hostname = CONFIG["MDNS_HOSTNAME"]
    # Remove .local suffix if already present to avoid double .local
    if hostname.endswith(".local"):
        hostname = hostname[:-6]

    # Try to get actual IP address for better compatibility
    try:
        # Get local IP that's not loopback
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return f"https://{local_ip}:{CONFIG['PORT']}"
    except Exception:
        # Fallback to hostname
        return f"https://{hostname}.local:{CONFIG['PORT']}"


def _list_directory(base_path, path=""):
    """
    List files in a single directory.

    Args:
        base_path: Absolute base directory
        path: Relative path within the base directory

    Returns:
        List of file/directory info dicts
    """
    full_path = os.path.realpath(os.path.join(base_path, path))

    # Guard against directory traversal
    if not full_path.startswith(os.path.realpath(base_path)):
        return []

    if not os.path.exists(full_path):
        return []

    items = []

    try:
        dir_entries = os.listdir(full_path)
    except (PermissionError, OSError) as e:
        print(f"Error listing directory {full_path}: {e}")
        return []

    for item in dir_entries:
        # Skip hidden files and macOS metadata files
        if item.startswith(".") or item.startswith("._"):
            continue

        item_path = os.path.join(full_path, item)
        rel_path = os.path.join(path, item) if path else item

        try:
            # Skip broken symlinks
            if os.path.islink(item_path) and not os.path.exists(item_path):
                continue

            stat = os.stat(item_path)
            is_directory = os.path.isdir(item_path)

            items.append(
                {
                    "id": rel_path,  # Use path as unique ID
                    "name": item,
                    "path": rel_path,
                    "type": "folder" if is_directory else "file",
                    "size": stat.st_size if not is_directory else 0,
                    "modifiedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "parentPath": "/" + path if path else "/",
                }
            )
        except (PermissionError, OSError, FileNotFoundError) as e:
            # Skip files we can't access
            print(f"Skipping {item}: {e}")
            continue

    return items


def get_file_list(path=""):
    """
    Get a list of files from the storage directory.

    All files live under a single ``files/`` subdirectory inside STORAGE_PATH.
    Access control is handled purely by the permission resolver – there is no
    longer a protected/unprotected split.

    Args:
        path: Relative path within the files directory.

    Returns:
        Sorted list of file/directory info dicts (folders first, then files).
    """
    files_base = os.path.join(CONFIG["STORAGE_PATH"], "files")

    # Ensure directory exists
    os.makedirs(files_base, exist_ok=True)

    items = _list_directory(files_base, path)

    # Sort: directories first, then files alphabetically
    items.sort(key=lambda x: (x["type"] != "folder", x["name"].lower()))

    return items


def resolve_file_path(rel_path):
    """Resolve a virtual path to the actual filesystem path.

    Looks in the ``files/`` subdirectory of STORAGE_PATH.  Returns the path
    if existing, or ``None``.

    Validates that the resolved path stays within the storage directory to
    prevent directory traversal attacks.
    """
    storage = Path(CONFIG["STORAGE_PATH"]).resolve()
    base = (storage / "files").resolve()
    candidate = (base / rel_path).resolve()
    # Guard against directory traversal (e.g. ../../etc/passwd)
    if not str(candidate).startswith(str(base)):
        return None
    if candidate.exists():
        return candidate
    return None


# =============================================================================
# REST API v1 Endpoints
# =============================================================================


@app.route("/api/v1/auth/login", methods=["POST"])
def api_login():
    """Authenticate user and return JWT token."""
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required", "code": "MISSING_BODY"}), 400

    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password required", "code": "MISSING_CREDENTIALS"}), 400

    # Authenticate user
    user = auth.authenticate_user(email, password)

    if not user:
        log_audit(
            "auth.login_failed",
            target_type="user",
            description=f"Failed login attempt for {email}",
            status="failure",
            user_email=email,
        )
        return jsonify({"error": "Invalid credentials", "code": "INVALID_CREDENTIALS"}), 401

    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()

    # Generate JWT token
    token = auth.generate_session_token(user)

    log_audit(
        "auth.login",
        target_type="user",
        target_id=user.id,
        description=f"User {user.email} logged in",
        user_id=user.id,
        user_email=user.email,
    )

    return jsonify({"token": token, "user": user.to_dict()}), 200


@app.route("/api/v1/auth/signup", methods=["POST"])
def api_signup():
    """Register new user account.

    Only emails whose domain appears in the system-settings domain allowlist
    (or that were pre-created by an admin) are accepted.  All other signups
    are rejected with a 403.
    """
    from models import SystemSettings

    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required", "code": "MISSING_BODY"}), 400

    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    data.get("username", "").strip()

    # Validation
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required", "code": "INVALID_EMAIL"}), 400

    if not password or len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters", "code": "INVALID_PASSWORD"}), 400

    # Check if email already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        # Allow claiming a pre-approved account (admin pre-created, still on temp password)
        if existing_user.is_approved and existing_user.is_default_pin:
            # Claim the pre-approved account: set the user's chosen password
            existing_user.password_hash = auth.hash_password(password)
            existing_user.is_default_pin = False
            existing_user.last_login = datetime.utcnow()
            db.session.commit()
            token = auth.generate_session_token(existing_user)
            return jsonify({"token": token, "user": existing_user.to_dict()}), 200
        return jsonify({"error": "Email already registered", "code": "EMAIL_EXISTS"}), 409

    # Check domain allowlist (SystemSettings legacy + DomainConfig)
    email_domain = email.rsplit("@", 1)[1].lower()
    settings = SystemSettings.query.first()
    allowed = [d.strip().lower() for d in (settings.allowed_domains or "").split(",") if d.strip()] if settings else []

    # Also allow if domain has a DomainConfig entry
    domain_cfg_exists = DomainConfig.query.filter_by(domain=email_domain).first() is not None

    if email_domain not in allowed and not domain_cfg_exists:
        return jsonify(
            {
                "error": "Registration is not open for this email domain. Contact your administrator.",
                "code": "DOMAIN_NOT_ALLOWED",
            }
        ), 403

    # Create new user (domain-allowlisted: auto-approved for protected files)
    new_user = User(
        email=email, password_hash=auth.hash_password(password), role="user", is_default_pin=False, is_approved=True
    )
    db.session.add(new_user)
    db.session.commit()

    # Send approval email with .p12 client certificate and store cert metadata
    if settings and settings.smtp_enabled:
        _ok, _err, cert_meta = send_approval_email(
            new_user.email,
            settings.device_name or "TerraCrate",
            settings,
            ca_cert_path=CONFIG["CERT_PATH"],
            ca_key_path=CONFIG["KEY_PATH"],
        )
        if cert_meta:
            new_user.cert_serial_number = format(cert_meta["serial"], "x")
            new_user.cert_issued_at = cert_meta["not_before"]
            new_user.cert_expires_at = cert_meta["not_after"]
            db.session.commit()

    # Generate token for immediate login
    token = auth.generate_session_token(new_user)

    log_audit(
        "auth.signup",
        target_type="user",
        target_id=new_user.id,
        description=f"New signup: {new_user.email}",
        user_id=new_user.id,
        user_email=new_user.email,
    )

    return jsonify({"token": token, "user": new_user.to_dict()}), 201


@app.route("/api/v1/auth/logout", methods=["POST"])
@auth.require_auth()
def api_logout():
    """Logout current user."""
    log_audit("auth.logout", description="User logged out")
    # JWT tokens are stateless, so we just return success
    # Frontend should delete the token
    return jsonify({"success": True}), 200


@app.route("/api/v1/auth/me", methods=["GET"])
@auth.require_auth()
def api_get_current_user():
    """Get current authenticated user info."""
    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)

    if not user:
        return jsonify({"error": "User not found", "code": "USER_NOT_FOUND"}), 404

    return jsonify({"user": user.to_dict(include_permissions=True)}), 200


@app.route("/api/v1/auth/refresh", methods=["POST"])
@auth.require_auth()
def api_refresh_token():
    """Refresh JWT token."""
    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)

    if not user:
        return jsonify({"error": "Invalid token", "code": "INVALID_TOKEN"}), 401

    # Generate new token
    new_token = auth.generate_session_token(user)

    return jsonify({"token": new_token}), 200


@app.route("/api/v1/auth/change-password", methods=["POST"])
@auth.require_auth()
def api_change_password():
    """Change user password."""
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required", "code": "MISSING_BODY"}), 400

    current_password = data.get("currentPassword", "").strip()
    new_password = data.get("newPassword", "").strip()

    if not new_password or len(new_password) < 6:
        return jsonify({"error": "New password must be at least 6 characters", "code": "INVALID_PASSWORD"}), 400

    # Get current user
    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)

    if not user:
        return jsonify({"error": "User not found", "code": "USER_NOT_FOUND"}), 404

    # For first-time password change, allow skipping current password check
    if not user.is_default_pin:
        if not current_password:
            return jsonify({"error": "Current password required", "code": "MISSING_CURRENT_PASSWORD"}), 400

        # Verify current password
        if not auth.verify_password(current_password, user.password_hash):
            return jsonify({"error": "Current password is incorrect", "code": "INVALID_CURRENT_PASSWORD"}), 401

    # Update password
    user.password_hash = auth.hash_password(new_password)
    user.is_default_pin = False  # Clear the flag
    db.session.commit()

    log_audit(
        "auth.password_change",
        target_type="user",
        target_id=user.id,
        description="Password changed",
        user_id=user.id,
        user_email=user.email,
    )

    # Generate new token
    new_token = auth.generate_session_token(user)

    return jsonify({"token": new_token, "user": user.to_dict()}), 200


@app.route("/api/v1/settings", methods=["GET"])
def api_get_settings():
    """Get system settings (public endpoint)."""
    from models import SystemSettings

    settings = SystemSettings.query.first()
    if not settings:
        return jsonify({"error": "Settings not found", "code": "SETTINGS_NOT_FOUND"}), 404

    return jsonify(settings.to_dict()), 200


@app.route("/api/v1/settings", methods=["PUT"])
@auth.require_admin()
def api_update_settings():
    """Update system settings (admin only)."""
    from models import SystemSettings

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required", "code": "MISSING_BODY"}), 400

    settings = SystemSettings.query.first()
    if not settings:
        return jsonify({"error": "Settings not found", "code": "SETTINGS_NOT_FOUND"}), 404

    # Update allowed fields (mode toggle removed – access is now directory-based)
    if "authMethod" in data:
        if data["authMethod"] not in ["email", "email+password", "username+password"]:
            return jsonify({"error": "Invalid authMethod value", "code": "INVALID_AUTH_METHOD"}), 400
        settings.auth_method = data["authMethod"]

    if "tlsEnabled" in data:
        settings.tls_enabled = bool(data["tlsEnabled"])

    if "httpsPort" in data:
        port = int(data["httpsPort"])
        if port < 1 or port > 65535:
            return jsonify({"error": "Invalid port number", "code": "INVALID_PORT"}), 400
        settings.https_port = port

    if "deviceName" in data:
        settings.device_name = data["deviceName"].strip()

    # SMTP settings
    if "smtpEnabled" in data:
        settings.smtp_enabled = bool(data["smtpEnabled"])
    if "smtpHost" in data:
        settings.smtp_host = data["smtpHost"].strip()
    if "smtpPort" in data:
        port = int(data["smtpPort"])
        if port < 1 or port > 65535:
            return jsonify({"error": "Invalid SMTP port number", "code": "INVALID_SMTP_PORT"}), 400
        settings.smtp_port = port
    if "smtpUsername" in data:
        settings.smtp_username = data["smtpUsername"].strip()
    if "smtpPassword" in data:
        # Only update password if it's not the masked placeholder
        if data["smtpPassword"] != "*****":
            settings.smtp_password = data["smtpPassword"]
    if "smtpFromEmail" in data:
        settings.smtp_from_email = data["smtpFromEmail"].strip()
    if "smtpUseTls" in data:
        settings.smtp_use_tls = bool(data["smtpUseTls"])

    # Domain allowlist
    if "allowedDomains" in data:
        domains = data["allowedDomains"]
        if not isinstance(domains, list):
            return jsonify({"error": "allowedDomains must be a list", "code": "INVALID_DOMAINS"}), 400
        # Validate and normalize each domain (strip whitespace, remove leading @)
        cleaned = []
        for d in domains:
            d = str(d).strip().lstrip("@").lower()
            if not d or "." not in d:
                return jsonify({"error": f"Invalid domain: {d}", "code": "INVALID_DOMAIN"}), 400
            cleaned.append(d)
        settings.allowed_domains = ",".join(cleaned)

        # Auto-create DomainConfig (with an empty permission entry) for any
        # newly-added domains so they appear immediately on the Domains page.
        existing = {dc.domain for dc in DomainConfig.query.all()}
        for d in cleaned:
            if d not in existing:
                dc = DomainConfig(domain=d)
                db.session.add(dc)

    settings.updated_at = datetime.utcnow()
    db.session.commit()

    log_audit("settings.update", target_type="settings", description="System settings updated")

    return jsonify(settings.to_dict()), 200


@app.route("/api/v1/users", methods=["GET"])
@auth.require_admin()
def api_list_users():
    """List all users with optional search and pagination (admin only)."""
    search = request.args.get("search", "").strip()
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))

    query = User.query

    if search:
        query = query.filter(User.email.ilike(f"%{search}%"))

    # Paginate
    total = query.count()
    users = query.offset((page - 1) * limit).limit(limit).all()

    return jsonify(
        {
            "users": [user.to_dict(include_permissions=True) for user in users],
            "total": total,
            "page": page,
            "limit": limit,
        }
    ), 200


@app.route("/api/v1/users", methods=["POST"])
@auth.require_admin()
def api_create_user():
    """Create new user (admin only)."""
    from models import SystemSettings

    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body required", "code": "MISSING_BODY"}), 400

    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    role = data.get("role", "user").strip()

    # Validation
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required", "code": "INVALID_EMAIL"}), 400

    if role not in ["admin", "user"]:
        return jsonify({"error": "Invalid role", "code": "INVALID_ROLE"}), 400

    # Check if email already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        # Approve the existing user for protected file access
        was_approved = existing_user.is_approved
        existing_user.is_approved = True
        if role:
            existing_user.role = role
        db.session.commit()

        # Send approval email if user was not previously approved
        if not was_approved:
            settings = SystemSettings.query.first()
            if settings and settings.smtp_enabled:
                _ok, _err, cert_meta = send_approval_email(
                    existing_user.email,
                    settings.device_name or "TerraCrate",
                    settings,
                    ca_cert_path=CONFIG["CERT_PATH"],
                    ca_key_path=CONFIG["KEY_PATH"],
                )
                if cert_meta:
                    existing_user.cert_serial_number = format(cert_meta["serial"], "x")
                    existing_user.cert_issued_at = cert_meta["not_before"]
                    existing_user.cert_expires_at = cert_meta["not_after"]
                    existing_user.cert_revoked = False
                    db.session.commit()

        return jsonify({"user": existing_user.to_dict(include_permissions=True), "approved": True}), 200

    # Generate client certificate; use the .p12 password as the initial login password
    # so the user can log in (instead of signing up) and will be prompted to change it.
    p12_bytes = None
    p12_password = None
    cert_serial = None
    cert_not_before = None
    cert_not_after = None
    settings = SystemSettings.query.first()
    try:
        p12_bytes, p12_password, cert_serial, cert_not_before, cert_not_after = generate_client_p12(
            CONFIG["CERT_PATH"], CONFIG["KEY_PATH"], email
        )
    except Exception:
        import logging

        logging.getLogger(__name__).error("Failed to generate client cert for %s", email, exc_info=True)

    initial_password = password if password else (p12_password or "changeme")

    # Create user (admin-created users are pre-approved for protected files)
    new_user = User(
        email=email,
        password_hash=auth.hash_password(initial_password),
        role=role,
        is_default_pin=True,
        is_approved=True,
        cert_serial_number=format(cert_serial, "x") if cert_serial else None,
        cert_issued_at=cert_not_before,
        cert_expires_at=cert_not_after,
    )
    db.session.add(new_user)
    db.session.commit()

    # Send invite email for pre-created account
    if settings and settings.smtp_enabled:
        send_invite_email(
            new_user.email,
            settings.device_name or "TerraCrate",
            settings,
            p12_data=(p12_bytes, p12_password) if p12_bytes else None,
        )

    log_audit("user.create", target_type="user", target_id=new_user.id, description=f"Created user {new_user.email}")

    return jsonify({"user": new_user.to_dict()}), 201


@app.route("/api/v1/users/<int:user_id>", methods=["GET"])
@auth.require_admin()
def api_get_user(user_id):
    """Get user by ID (admin only)."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found", "code": "USER_NOT_FOUND"}), 404

    return jsonify({"user": user.to_dict(include_permissions=True)}), 200


@app.route("/api/v1/users/<int:user_id>", methods=["PUT"])
@auth.require_admin()
def api_update_user(user_id):
    """Update user (admin only)."""
    from models import SystemSettings

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found", "code": "USER_NOT_FOUND"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required", "code": "MISSING_BODY"}), 400

    # Update allowed fields
    if "email" in data:
        email = data["email"].strip()
        if not email or "@" not in email:
            return jsonify({"error": "Valid email required", "code": "INVALID_EMAIL"}), 400

        # Check if email is taken by another user
        existing = User.query.filter_by(email=email).first()
        if existing and existing.id != user_id:
            return jsonify({"error": "Email already exists", "code": "EMAIL_EXISTS"}), 409

        user.email = email

    if "password" in data and data["password"]:
        if len(data["password"]) < 6:
            return jsonify({"error": "Password must be at least 6 characters", "code": "INVALID_PASSWORD"}), 400
        user.password_hash = auth.hash_password(data["password"])

    if "role" in data:
        if data["role"] not in ["admin", "user"]:
            return jsonify({"error": "Invalid role", "code": "INVALID_ROLE"}), 400
        user.role = data["role"]

    if "approved" in data:
        was_approved = user.is_approved
        user.is_approved = bool(data["approved"])

    db.session.commit()

    # Send approval email if user was just approved
    if "approved" in data and bool(data["approved"]) and not was_approved:
        settings = SystemSettings.query.first()
        if settings and settings.smtp_enabled:
            _ok, _err, cert_meta = send_approval_email(
                user.email,
                settings.device_name or "TerraCrate",
                settings,
                ca_cert_path=CONFIG["CERT_PATH"],
                ca_key_path=CONFIG["KEY_PATH"],
            )
            if cert_meta:
                user.cert_serial_number = format(cert_meta["serial"], "x")
                user.cert_issued_at = cert_meta["not_before"]
                user.cert_expires_at = cert_meta["not_after"]
                user.cert_revoked = False
                db.session.commit()

    log_audit("user.update", target_type="user", target_id=user.id, description=f"Updated user {user.email}")

    return jsonify({"user": user.to_dict()}), 200


@app.route("/api/v1/users/<int:user_id>", methods=["DELETE"])
@auth.require_admin()
def api_delete_user(user_id):
    """Delete user (admin only)."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found", "code": "USER_NOT_FOUND"}), 404

    # Prevent deleting yourself
    token = auth.get_token_from_request()
    current_user = auth.get_user_from_token(token)
    if current_user and current_user.id == user_id:
        return jsonify({"error": "Cannot delete yourself", "code": "CANNOT_DELETE_SELF"}), 400

    deleted_email = user.email
    db.session.delete(user)
    db.session.commit()

    log_audit("user.delete", target_type="user", target_id=user_id, description=f"Deleted user {deleted_email}")

    return jsonify({"success": True}), 200


# ── Certificate Revocation & Re-issue ────────────────────────────────────────


def _rebuild_crl():
    """Rebuild the CRL file from all revoked certificates in the database."""
    entries = [
        {"serial_number": int(rc.serial_number, 16), "revoked_at": rc.revoked_at}
        for rc in RevokedCertificate.query.all()
    ]
    crl_bytes = generate_crl(CONFIG["CERT_PATH"], CONFIG["KEY_PATH"], entries)
    crl_path = os.path.join(os.path.dirname(CONFIG["CERT_PATH"]), "crl.pem")
    update_crl_file(crl_bytes, crl_path)


def _revoke_user_cert(user, reason, revoked_by_id=None):
    """Internal helper: revoke a user's current certificate.

    Returns the RevokedCertificate record, or None if user has no cert.
    """
    if not user.cert_serial_number:
        return None

    record = RevokedCertificate(
        serial_number=user.cert_serial_number,
        user_id=user.id,
        reason=reason,
        revoked_by=revoked_by_id,
    )
    db.session.add(record)

    user.cert_revoked = True
    user.cert_serial_number = None
    user.cert_issued_at = None
    user.cert_expires_at = None
    db.session.commit()

    _rebuild_crl()
    return record


@app.route("/api/v1/users/<int:user_id>/revoke-cert", methods=["POST"])
@auth.require_admin()
def api_revoke_cert(user_id):
    """Revoke a user's client certificate (admin only).

    The user's account and permissions are preserved.  File access via mTLS
    is blocked until a new certificate is re-issued.
    """
    from models import SystemSettings

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found", "code": "USER_NOT_FOUND"}), 404

    if user.cert_revoked or not user.cert_serial_number:
        return jsonify({"error": "User has no active certificate to revoke", "code": "NO_ACTIVE_CERT"}), 400

    token = auth.get_token_from_request()
    admin_user = auth.get_user_from_token(token)

    record = _revoke_user_cert(user, "admin_revoked", revoked_by_id=admin_user.id if admin_user else None)

    # Send notification email
    settings = SystemSettings.query.first()
    if settings and settings.smtp_enabled:
        send_revocation_email(user.email, settings.device_name or "TerraCrate", settings)

    log_audit("cert.revoke", target_type="user", target_id=user.id, description=f"Revoked certificate for {user.email}")

    return jsonify(
        {
            "message": f"Certificate revoked for {user.email}",
            "revokedSerial": record.serial_number if record else None,
            "user": user.to_dict(),
        }
    ), 200


@app.route("/api/v1/users/<int:user_id>/reissue-cert", methods=["POST"])
@auth.require_admin()
def api_reissue_cert(user_id):
    """Re-issue a client certificate for a user (admin only).

    The user's previous certificate must have been revoked first.  A new P12
    bundle is generated and emailed to the user.
    """
    from models import SystemSettings

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found", "code": "USER_NOT_FOUND"}), 404

    if user.cert_serial_number and not user.cert_revoked:
        return jsonify(
            {
                "error": "User already has an active certificate. Revoke it first.",
                "code": "CERT_STILL_ACTIVE",
            }
        ), 400

    # Generate new certificate
    try:
        p12_bytes, p12_password, serial, not_before, not_after = generate_client_p12(
            CONFIG["CERT_PATH"], CONFIG["KEY_PATH"], user.email
        )
    except Exception:
        import logging

        logging.getLogger(__name__).error("Failed to generate client cert for %s", user.email, exc_info=True)
        return jsonify({"error": "Failed to generate certificate", "code": "CERT_GEN_FAILED"}), 500

    user.cert_serial_number = format(serial, "x")
    user.cert_issued_at = not_before
    user.cert_expires_at = not_after
    user.cert_revoked = False
    db.session.commit()

    # Email new cert to user
    settings = SystemSettings.query.first()
    if settings and settings.smtp_enabled:
        send_invite_email(
            user.email,
            settings.device_name or "TerraCrate",
            settings,
            p12_data=(p12_bytes, p12_password),
        )

    log_audit(
        "cert.reissue", target_type="user", target_id=user.id, description=f"Reissued certificate for {user.email}"
    )

    return jsonify(
        {
            "message": f"New certificate issued for {user.email}",
            "user": user.to_dict(),
        }
    ), 200


@app.route("/api/v1/users/<int:user_id>/cert-status", methods=["GET"])
@auth.require_admin()
def api_cert_status(user_id):
    """Get certificate status and revocation history for a user (admin only)."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found", "code": "USER_NOT_FOUND"}), 404

    history = RevokedCertificate.query.filter_by(user_id=user_id).order_by(RevokedCertificate.revoked_at.desc()).all()

    return jsonify(
        {
            "serial": user.cert_serial_number,
            "issuedAt": user.cert_issued_at.isoformat() if user.cert_issued_at else None,
            "expiresAt": user.cert_expires_at.isoformat() if user.cert_expires_at else None,
            "isRevoked": user.cert_revoked,
            "revocationHistory": [r.to_dict() for r in history],
        }
    ), 200


@app.route("/api/v1/users/<int:user_id>/permissions", methods=["GET"])
@auth.require_admin()
def api_get_user_permissions(user_id):
    """Get user folder permissions (admin only)."""
    from models import FolderPermission

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found", "code": "USER_NOT_FOUND"}), 404

    permissions = FolderPermission.query.filter_by(user_id=user_id).all()

    return jsonify({"permissions": [p.to_dict() for p in permissions]}), 200


@app.route("/api/v1/users/<int:user_id>/permissions", methods=["PUT"])
@auth.require_admin()
def api_update_user_permissions(user_id):
    """Update user folder permissions (admin only)."""
    from models import FolderPermission

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found", "code": "USER_NOT_FOUND"}), 404

    data = request.get_json()
    if not data or "permissions" not in data:
        return jsonify({"error": "Permissions array required", "code": "MISSING_PERMISSIONS"}), 400

    # Delete existing permissions
    FolderPermission.query.filter_by(user_id=user_id).delete()

    # Add new permissions — only create rows where at least one flag is set
    valid_states = {"allow", "deny"}
    for perm_data in data["permissions"]:
        read_val = perm_data.get("read")  # "allow", "deny", or null/missing
        write_val = perm_data.get("write")  # "allow", "deny", or null/missing

        # Normalise: only keep valid tri-state strings; everything else is None
        read_val = read_val if read_val in valid_states else None
        write_val = write_val if write_val in valid_states else None

        # Skip rows where both flags are None (no action on either)
        if read_val is None and write_val is None:
            continue

        permission = FolderPermission(
            user_id=user_id,
            folder_path=perm_data.get("path", "/"),
            can_read=read_val,
            can_write=write_val,
        )
        db.session.add(permission)

    db.session.commit()

    log_audit(
        "permission.user_update",
        target_type="user",
        target_id=user_id,
        description=f"Updated permissions for {user.email}",
    )

    # Return updated permissions
    permissions = FolderPermission.query.filter_by(user_id=user_id).all()
    return jsonify({"permissions": [p.to_dict() for p in permissions]}), 200


@app.route("/api/v1/folders", methods=["GET"])
@auth.require_admin()
def api_list_folders():
    """List all folders from the files subdirectory (admin only).

    Root is intentionally excluded — permissions are per-folder only.
    """
    folders = []

    files_path = Path(CONFIG["STORAGE_PATH"]) / "files"
    if not files_path.exists():
        return jsonify({"folders": folders}), 200

    try:
        for item in files_path.rglob("*"):
            if item.is_dir():
                rel_path = "/" + str(item.relative_to(files_path))
                folders.append({"path": rel_path, "name": item.name})
    except Exception as e:
        return jsonify({"error": str(e), "code": "FOLDER_SCAN_ERROR"}), 500

    return jsonify({"folders": folders}), 200


# =============================================================================
# Domain Config Endpoints (admin only)
# =============================================================================


@app.route("/api/v1/domains", methods=["GET"])
@auth.require_admin()
def api_list_domains():
    """List all domain configs with their permissions.

    Auto-creates DomainConfig rows for any domains in system settings'
    allowed_domains that don't already have one, so the admin sees them
    prepopulated and ready to configure.
    """
    from models import SystemSettings

    settings = SystemSettings.query.first()
    if settings and settings.allowed_domains:
        allowed = [d.strip().lower() for d in settings.allowed_domains.split(",") if d.strip()]
        existing = {dc.domain for dc in DomainConfig.query.all()}
        created = False
        for domain in allowed:
            if domain not in existing:
                db.session.add(DomainConfig(domain=domain))
                created = True
        if created:
            db.session.commit()

    domains = DomainConfig.query.order_by(DomainConfig.domain).all()
    return jsonify({"domains": [d.to_dict() for d in domains]}), 200


@app.route("/api/v1/domains", methods=["POST"])
@auth.require_admin()
def api_create_domain():
    """Create a new domain config with optional permissions."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required", "code": "MISSING_BODY"}), 400

    domain = data.get("domain", "").strip().lower().lstrip("@")
    if not domain or "." not in domain:
        return jsonify({"error": "Valid domain required", "code": "INVALID_DOMAIN"}), 400

    if DomainConfig.query.filter_by(domain=domain).first():
        return jsonify({"error": "Domain already exists", "code": "DOMAIN_EXISTS"}), 409

    dc = DomainConfig(domain=domain)
    db.session.add(dc)
    db.session.flush()  # get dc.id

    for perm_data in data.get("permissions", []):
        dp = DomainPermission(
            domain_id=dc.id,
            folder_path=perm_data.get("path", "/"),
            can_read=perm_data.get("read", False),
            can_write=perm_data.get("write", False),
        )
        db.session.add(dp)

    db.session.commit()

    log_audit("domain.create", target_type="domain", target_id=dc.id, description=f"Created domain {dc.domain}")

    return jsonify({"domain": dc.to_dict()}), 201


@app.route("/api/v1/domains/<int:domain_id>", methods=["GET"])
@auth.require_admin()
def api_get_domain(domain_id):
    """Get a single domain config with permissions."""
    dc = DomainConfig.query.get(domain_id)
    if not dc:
        return jsonify({"error": "Domain not found", "code": "DOMAIN_NOT_FOUND"}), 404
    return jsonify({"domain": dc.to_dict()}), 200


@app.route("/api/v1/domains/<int:domain_id>", methods=["PUT"])
@auth.require_admin()
def api_update_domain(domain_id):
    """Update a domain config (domain name and/or permissions)."""
    dc = DomainConfig.query.get(domain_id)
    if not dc:
        return jsonify({"error": "Domain not found", "code": "DOMAIN_NOT_FOUND"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required", "code": "MISSING_BODY"}), 400

    if "domain" in data:
        new_domain = data["domain"].strip().lower().lstrip("@")
        if not new_domain or "." not in new_domain:
            return jsonify({"error": "Valid domain required", "code": "INVALID_DOMAIN"}), 400
        existing = DomainConfig.query.filter_by(domain=new_domain).first()
        if existing and existing.id != domain_id:
            return jsonify({"error": "Domain already exists", "code": "DOMAIN_EXISTS"}), 409
        dc.domain = new_domain

    if "permissions" in data:
        DomainPermission.query.filter_by(domain_id=dc.id).delete()
        for perm_data in data["permissions"]:
            dp = DomainPermission(
                domain_id=dc.id,
                folder_path=perm_data.get("path", "/"),
                can_read=perm_data.get("read", False),
                can_write=perm_data.get("write", False),
            )
            db.session.add(dp)

    db.session.commit()

    log_audit("domain.update", target_type="domain", target_id=dc.id, description=f"Updated domain {dc.domain}")

    return jsonify({"domain": dc.to_dict()}), 200


@app.route("/api/v1/domains/<int:domain_id>", methods=["DELETE"])
@auth.require_admin()
def api_delete_domain(domain_id):
    """Delete a domain config and its permissions."""
    dc = DomainConfig.query.get(domain_id)
    if not dc:
        return jsonify({"error": "Domain not found", "code": "DOMAIN_NOT_FOUND"}), 404

    deleted_domain = dc.domain
    db.session.delete(dc)
    db.session.commit()

    log_audit(
        "domain.delete", target_type="domain", target_id=domain_id, description=f"Deleted domain {deleted_domain}"
    )

    return jsonify({"success": True}), 200


# =============================================================================
# Group Endpoints (admin only)
# =============================================================================


@app.route("/api/v1/groups", methods=["GET"])
@auth.require_admin()
def api_list_groups():
    """List all groups with member count and permission count."""
    groups = Group.query.order_by(Group.name).all()
    return jsonify({"groups": [g.to_dict() for g in groups]}), 200


@app.route("/api/v1/groups", methods=["POST"])
@auth.require_admin()
def api_create_group():
    """Create a new group."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required", "code": "MISSING_BODY"}), 400

    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Group name required", "code": "MISSING_NAME"}), 400

    if Group.query.filter_by(name=name).first():
        return jsonify({"error": "Group name already exists", "code": "GROUP_EXISTS"}), 409

    grp = Group(name=name, description=data.get("description", "").strip() or None)
    db.session.add(grp)
    db.session.commit()

    log_audit("group.create", target_type="group", target_id=grp.id, description=f"Created group {grp.name}")

    return jsonify({"group": grp.to_dict()}), 201


@app.route("/api/v1/groups/<int:group_id>", methods=["GET"])
@auth.require_admin()
def api_get_group(group_id):
    """Get a single group with members and permissions."""
    grp = Group.query.get(group_id)
    if not grp:
        return jsonify({"error": "Group not found", "code": "GROUP_NOT_FOUND"}), 404
    return jsonify({"group": grp.to_dict(include_members=True)}), 200


@app.route("/api/v1/groups/<int:group_id>", methods=["PUT"])
@auth.require_admin()
def api_update_group(group_id):
    """Update group metadata (name, description)."""
    grp = Group.query.get(group_id)
    if not grp:
        return jsonify({"error": "Group not found", "code": "GROUP_NOT_FOUND"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required", "code": "MISSING_BODY"}), 400

    if "name" in data:
        new_name = data["name"].strip()
        if not new_name:
            return jsonify({"error": "Group name required", "code": "MISSING_NAME"}), 400
        existing = Group.query.filter_by(name=new_name).first()
        if existing and existing.id != group_id:
            return jsonify({"error": "Group name already exists", "code": "GROUP_EXISTS"}), 409
        grp.name = new_name

    if "description" in data:
        grp.description = data["description"].strip() or None

    db.session.commit()

    log_audit("group.update", target_type="group", target_id=grp.id, description=f"Updated group {grp.name}")

    return jsonify({"group": grp.to_dict(include_members=True)}), 200


@app.route("/api/v1/groups/<int:group_id>", methods=["DELETE"])
@auth.require_admin()
def api_delete_group(group_id):
    """Delete a group (cascades memberships and permissions)."""
    grp = Group.query.get(group_id)
    if not grp:
        return jsonify({"error": "Group not found", "code": "GROUP_NOT_FOUND"}), 404

    deleted_name = grp.name
    db.session.delete(grp)
    db.session.commit()

    log_audit("group.delete", target_type="group", target_id=group_id, description=f"Deleted group {deleted_name}")

    return jsonify({"success": True}), 200


@app.route("/api/v1/groups/<int:group_id>/permissions", methods=["PUT"])
@auth.require_admin()
def api_update_group_permissions(group_id):
    """Replace a group's permissions."""
    grp = Group.query.get(group_id)
    if not grp:
        return jsonify({"error": "Group not found", "code": "GROUP_NOT_FOUND"}), 404

    data = request.get_json()
    if not data or "permissions" not in data:
        return jsonify({"error": "Permissions array required", "code": "MISSING_PERMISSIONS"}), 400

    GroupPermission.query.filter_by(group_id=group_id).delete()
    for perm_data in data["permissions"]:
        gp = GroupPermission(
            group_id=group_id,
            folder_path=perm_data.get("path", "/"),
            can_read=perm_data.get("read", False),
            can_write=perm_data.get("write", False),
        )
        db.session.add(gp)

    db.session.commit()
    perms = GroupPermission.query.filter_by(group_id=group_id).all()

    log_audit(
        "permission.group_update",
        target_type="group",
        target_id=grp.id,
        description=f"Updated permissions for group {grp.name}",
    )

    return jsonify({"permissions": [p.to_dict() for p in perms]}), 200


@app.route("/api/v1/groups/<int:group_id>/members", methods=["PUT"])
@auth.require_admin()
def api_update_group_members(group_id):
    """Replace a group's member list."""
    grp = Group.query.get(group_id)
    if not grp:
        return jsonify({"error": "Group not found", "code": "GROUP_NOT_FOUND"}), 404

    data = request.get_json()
    if not data or "userIds" not in data:
        return jsonify({"error": "userIds array required", "code": "MISSING_USER_IDS"}), 400

    GroupMembership.query.filter_by(group_id=group_id).delete()
    for uid in data["userIds"]:
        user = User.query.get(uid)
        if user:
            db.session.add(GroupMembership(group_id=group_id, user_id=uid))

    db.session.commit()
    # Refresh to get updated members
    db.session.refresh(grp)

    log_audit(
        "group.members_update",
        target_type="group",
        target_id=grp.id,
        description=f"Updated members for group {grp.name}",
    )

    return jsonify({"group": grp.to_dict(include_members=True)}), 200


# =============================================================================
# Enhanced User Permission Endpoints
# =============================================================================


@app.route("/api/v1/users/<int:user_id>/effective-permissions", methods=["GET"])
@auth.require_admin()
def api_get_effective_permissions(user_id):
    """Get a user's effective resolved permissions with source attribution."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found", "code": "USER_NOT_FOUND"}), 404

    detailed = resolve_permissions_detailed(user)
    return jsonify({"permissions": detailed}), 200


@app.route("/api/v1/users/<int:user_id>/groups", methods=["PUT"])
@auth.require_admin()
def api_update_user_groups(user_id):
    """Assign a user to groups."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found", "code": "USER_NOT_FOUND"}), 404

    data = request.get_json()
    if not data or "groupIds" not in data:
        return jsonify({"error": "groupIds array required", "code": "MISSING_GROUP_IDS"}), 400

    GroupMembership.query.filter_by(user_id=user_id).delete()
    for gid in data["groupIds"]:
        grp = Group.query.get(gid)
        if grp:
            db.session.add(GroupMembership(group_id=gid, user_id=user_id))

    db.session.commit()
    db.session.refresh(user)

    log_audit(
        "permission.user_update",
        target_type="user",
        target_id=user.id,
        description=f"Updated group membership for {user.email}",
    )

    return jsonify({"user": user.to_dict(include_permissions=True)}), 200


def user_has_access(user, folder_path, require_write=False):
    """Check if a user can access a folder.

    Delegates to the layered permission resolver which merges domain defaults,
    group permissions, and user-level overrides.  If no permissions exist at
    any tier the user gets full default access (backward compatible).
    """

    return check_access(user, folder_path, require_write=require_write)


def _require_mtls_for_protected(user):
    """Return an error response if a non-admin user lacks a valid client cert.

    nginx forwards ``X-SSL-Client-Verify`` (``SUCCESS`` when the client
    presented a certificate verified against the CA) and ``X-SSL-Client-S-DN``
    (the certificate subject DN, e.g. ``O=terracrate,OU=member,CN=user@example.com``).

    This function also verifies that the certificate's CN matches the
    authenticated user's email so that one user's cert cannot be used to
    access another user's session.  Admin users are exempt (JWT-only auth).
    """
    if user and user.role != "admin":
        client_verify = request.headers.get("X-SSL-Client-Verify", "")
        if client_verify != "SUCCESS":
            return jsonify(
                {
                    "error": "A valid client certificate is required. Please install your .p12 certificate.",
                    "code": "CLIENT_CERT_REQUIRED",
                }
            ), 403

        # Verify the cert's CN matches the logged-in user's email
        client_dn = request.headers.get("X-SSL-Client-S-DN", "")
        cn_value = None
        for part in client_dn.split(","):
            part = part.strip()
            if part.upper().startswith("CN="):
                cn_value = part[3:].strip()
                break
        if not cn_value or cn_value.lower() != user.email.lower():
            # Log the mismatch for abuse detection
            _log_cn_mismatch(cn_value, user.id)
            return jsonify(
                {
                    "error": "Client certificate does not match your account. Please install the correct .p12 certificate.",
                    "code": "CLIENT_CERT_MISMATCH",
                }
            ), 403
    return None


# CN mismatch abuse detection settings
CN_MISMATCH_THRESHOLD = int(os.getenv("CN_MISMATCH_THRESHOLD", "3"))
CN_MISMATCH_WINDOW_MINUTES = int(os.getenv("CN_MISMATCH_WINDOW_MINUTES", "60"))


def _log_cn_mismatch(presented_cn, authenticated_user_id):
    """Log a CN mismatch and auto-revoke the abused cert if threshold exceeded."""
    import logging

    logger = logging.getLogger(__name__)

    if not presented_cn:
        return

    log_entry = MtlsMismatchLog(
        presented_cn=presented_cn,
        authenticated_user_id=authenticated_user_id,
    )
    db.session.add(log_entry)
    db.session.commit()

    log_audit(
        "cert.mtls_mismatch",
        target_type="user",
        target_id=authenticated_user_id,
        description=f"mTLS CN mismatch: presented {presented_cn}",
        status="failure",
        user_id=authenticated_user_id,
    )

    # Count recent mismatches for this CN within the time window
    window_start = datetime.utcnow() - timedelta(minutes=CN_MISMATCH_WINDOW_MINUTES)
    count = MtlsMismatchLog.query.filter(
        MtlsMismatchLog.presented_cn == presented_cn,
        MtlsMismatchLog.timestamp >= window_start,
    ).count()

    if count >= CN_MISMATCH_THRESHOLD:
        # Auto-revoke the cert belonging to the CN email (the cert being abused)
        abused_user = User.query.filter_by(email=presented_cn).first()
        if abused_user and abused_user.cert_serial_number and not abused_user.cert_revoked:
            logger.warning(
                "Auto-revoking cert for %s due to %d CN mismatches in %d minutes",
                presented_cn,
                count,
                CN_MISMATCH_WINDOW_MINUTES,
            )
            _revoke_user_cert(abused_user, "cn_mismatch_abuse")


# =============================================================================
# Guest File Endpoints (no authentication required)
# =============================================================================


def _guest_list_directory(path=""):
    """List files from the guest storage directory."""
    guest_base = os.path.join(CONFIG["GUEST_STORAGE_PATH"], "files")
    os.makedirs(guest_base, exist_ok=True)
    items = _list_directory(guest_base, path)
    items.sort(key=lambda x: (x["type"] != "folder", x["name"].lower()))
    return items


def _resolve_guest_file_path(rel_path):
    """Resolve a virtual path to the guest storage filesystem path."""
    base = Path(CONFIG["GUEST_STORAGE_PATH"]).resolve() / "files"
    candidate = (base / rel_path).resolve()
    if not str(candidate).startswith(str(base)):
        return None
    if candidate.exists():
        return candidate
    return None


@app.route("/api/v1/guest/files", methods=["GET"])
def api_guest_list_files():
    """List files available to guests (no authentication required, read-only)."""
    path = request.args.get("path", "")
    search = request.args.get("search", "").strip()

    try:
        files = _guest_list_directory(path)

        if search:
            files = [f for f in files if search.lower() in f["name"].lower()]

        return jsonify(
            {
                "files": files,
                "currentPath": "/" + path if path else "/",
                "parentPath": "/" + str(Path(path).parent) if path and path != "." else None,
            }
        ), 200
    except Exception as e:
        return jsonify({"error": str(e), "code": "FILE_LIST_ERROR"}), 500


@app.route("/api/v1/guest/files/download", methods=["GET"])
def api_guest_download_file():
    """Download a file from guest storage (no authentication required)."""
    path = request.args.get("path", "")
    if not path:
        return jsonify({"error": "Path required", "code": "MISSING_PATH"}), 400

    file_path = _resolve_guest_file_path(path)

    if not file_path or not file_path.is_file():
        return jsonify({"error": "File not found", "code": "FILE_NOT_FOUND"}), 404

    log_audit("file.guest_download", target_type="file", target_id=path, description=f"Guest downloaded {path}")

    return send_file(str(file_path), as_attachment=True)


@app.route("/api/v1/files", methods=["GET"])
@auth.require_auth()
def api_list_files():
    """List files in directory.

    Requires authentication.  Admin users see everything; non-admin users
    only see items they have permission for (or folders that lead toward
    granted areas).
    """
    path = request.args.get("path", "")
    search = request.args.get("search", "").strip()

    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)

    # Require mTLS client certificate for non-admin users
    if user.role != "admin":
        mtls_err = _require_mtls_for_protected(user)
        if mtls_err:
            return mtls_err

    # Get file list
    try:
        files = get_file_list(path)

        # Non-admin: filter to only items the user can see
        if user.role != "admin":
            from core.permissions import is_item_visible, visible_paths

            granted = visible_paths(user)
            if not granted:
                files = []
            else:
                current = "/" + path if path else "/"
                filtered = []
                for f in files:
                    # Build the full path for this item
                    item_path = current.rstrip("/") + "/" + f["name"] if current != "/" else "/" + f["name"]
                    if is_item_visible(item_path, f["type"] == "folder", granted):
                        filtered.append(f)
                files = filtered

        # Filter by search if provided
        if search:
            files = [f for f in files if search.lower() in f["name"].lower()]

        return jsonify(
            {
                "files": files,
                "currentPath": "/" + path if path else "/",
                "parentPath": "/" + str(Path(path).parent) if path and path != "." else None,
            }
        ), 200
    except Exception as e:
        return jsonify({"error": str(e), "code": "FILE_LIST_ERROR"}), 500


@app.route("/api/v1/files/upload", methods=["POST"])
@auth.require_auth()
def api_upload_file():
    """Upload file to the storage directory (requires authentication)."""
    if not CONFIG["ENABLE_UPLOADS"]:
        return jsonify({"error": "Uploads are disabled", "code": "UPLOADS_DISABLED"}), 403

    path = request.form.get("path", "").strip().lstrip("/")

    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)

    # Require mTLS for non-admin users
    if user.role != "admin":
        mtls_err = _require_mtls_for_protected(user)
        if mtls_err:
            return mtls_err

    # Check write permissions (admin has full access)
    if user.role != "admin":
        check_path = "/" + path if path else "/"
        if not user_has_access(user, check_path, require_write=True):
            return jsonify({"error": "Write access denied", "code": "WRITE_ACCESS_DENIED"}), 403

    # Handle upload
    if "file" not in request.files:
        return jsonify({"error": "No file provided", "code": "NO_FILE"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected", "code": "NO_FILE"}), 400

    # Secure filename and save to the files subdirectory
    filename = secure_filename(file.filename)
    storage_base = Path(CONFIG["STORAGE_PATH"]).resolve() / "files"
    target_dir = (storage_base / path).resolve()
    # Guard against directory traversal
    if not str(target_dir).startswith(str(storage_base)):
        return jsonify({"error": "Invalid path", "code": "INVALID_PATH"}), 400
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename

    file.save(str(target_path))

    # Return file info
    stat = target_path.stat()
    file_rel_path = str(Path(path) / filename) if path else filename

    log_audit(
        "file.upload",
        target_type="file",
        target_id=file_rel_path,
        description=f"Uploaded {filename} to /{path}" if path else f"Uploaded {filename}",
    )

    return jsonify(
        {
            "file": {
                "name": filename,
                "path": file_rel_path,
                "size": stat.st_size,
                "modifiedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        }
    ), 201


@app.route("/api/v1/files/download", methods=["GET"])
@auth.require_auth()
def api_download_file():
    """Download file (requires authentication)."""
    path = request.args.get("path", "")
    if not path:
        return jsonify({"error": "Path required", "code": "MISSING_PATH"}), 400

    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)

    if user.role != "admin":
        # Require mTLS for non-admin users
        mtls_err = _require_mtls_for_protected(user)
        if mtls_err:
            return mtls_err
        # Check read permissions
        parent = str(Path(path).parent)
        folder_path = "/" if parent == "." else "/" + parent
        if not user_has_access(user, folder_path):
            return jsonify({"error": "Read access denied", "code": "READ_ACCESS_DENIED"}), 403

    # Resolve file
    file_path = resolve_file_path(path)

    if not file_path or not file_path.is_file():
        return jsonify({"error": "File not found", "code": "FILE_NOT_FOUND"}), 404

    log_audit("file.download", target_type="file", target_id=path, description=f"Downloaded {path}")

    return send_file(str(file_path), as_attachment=True)


@app.route("/api/v1/files/preview", methods=["GET"])
@auth.require_auth()
def api_preview_file():
    """Stream file inline for in-browser preview (requires authentication)."""
    import mimetypes

    path = request.args.get("path", "")
    if not path:
        return jsonify({"error": "Path required", "code": "MISSING_PATH"}), 400

    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)

    if user.role != "admin":
        mtls_err = _require_mtls_for_protected(user)
        if mtls_err:
            return mtls_err
        parent = str(Path(path).parent)
        folder_path = "/" if parent == "." else "/" + parent
        if not user_has_access(user, folder_path):
            return jsonify({"error": "Read access denied", "code": "READ_ACCESS_DENIED"}), 403

    file_path = resolve_file_path(path)
    if not file_path or not file_path.is_file():
        return jsonify({"error": "File not found", "code": "FILE_NOT_FOUND"}), 404

    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type:
        mime_type = "application/octet-stream"

    return send_file(str(file_path), as_attachment=False, mimetype=mime_type, conditional=True)


@app.route("/api/v1/files/mkdir", methods=["POST"])
@auth.require_auth()
def api_create_directory():
    """Create directory in the protected subdirectory (requires authentication)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required", "code": "MISSING_BODY"}), 400

    path = data.get("path", "").strip().lstrip("/")
    name = data.get("name", "").strip()

    if not name:
        return jsonify({"error": "Directory name required", "code": "MISSING_NAME"}), 400

    # Check permissions
    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)

    if user.role != "admin":
        mtls_err = _require_mtls_for_protected(user)
        if mtls_err:
            return mtls_err
        check_path = "/" + path if path else "/"
        if not user_has_access(user, check_path, require_write=True):
            return jsonify({"error": "Write access denied", "code": "WRITE_ACCESS_DENIED"}), 403

    # Create directory in files subdirectory
    storage_base = Path(CONFIG["STORAGE_PATH"]).resolve() / "files"
    target_dir = (storage_base / path / secure_filename(name)).resolve()
    # Guard against directory traversal
    if not str(target_dir).startswith(str(storage_base)):
        return jsonify({"error": "Invalid path", "code": "INVALID_PATH"}), 400

    try:
        target_dir.mkdir(parents=True, exist_ok=False)
        dir_rel_path = str(Path(path) / name) if path else name
        log_audit(
            "file.mkdir",
            target_type="file",
            target_id=dir_rel_path,
            description=f"Created directory {name} in /{path}" if path else f"Created directory {name}",
        )
        return jsonify({"folder": {"name": name, "path": dir_rel_path}}), 201
    except FileExistsError:
        return jsonify({"error": "Directory already exists", "code": "DIR_EXISTS"}), 409
    except Exception as e:
        return jsonify({"error": str(e), "code": "CREATE_DIR_ERROR"}), 500


@app.route("/api/v1/files", methods=["DELETE"])
@auth.require_auth()
def api_delete_file():
    """Delete file or directory (requires authentication)."""
    if not CONFIG["ENABLE_DELETE"]:
        return jsonify({"error": "Delete is disabled", "code": "DELETE_DISABLED"}), 403

    path = request.args.get("path", "")
    if not path:
        return jsonify({"error": "Path required", "code": "MISSING_PATH"}), 400

    # Check permissions
    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)

    if user.role != "admin":
        mtls_err = _require_mtls_for_protected(user)
        if mtls_err:
            return mtls_err
        check_path = "/" + str(Path(path).parent)
        if not user_has_access(user, check_path, require_write=True):
            return jsonify({"error": "Write access denied", "code": "WRITE_ACCESS_DENIED"}), 403

    # Resolve file in the correct subdirectory
    target_path = resolve_file_path(path)

    if not target_path or not target_path.exists():
        return jsonify({"error": "File not found", "code": "FILE_NOT_FOUND"}), 404

    try:
        if target_path.is_dir():
            import shutil

            shutil.rmtree(target_path)
        else:
            target_path.unlink()

        log_audit("file.delete", target_type="file", target_id=path, description=f"Deleted {path}")

        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"error": str(e), "code": "DELETE_ERROR"}), 500


@app.route("/api/v1/files/rename", methods=["POST"])
@auth.require_auth()
def api_rename_file():
    """Rename a file or directory (requires authentication)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required", "code": "MISSING_BODY"}), 400

    path = data.get("path", "").strip().lstrip("/")
    new_name = data.get("newName", "").strip()

    if not path:
        return jsonify({"error": "Path required", "code": "MISSING_PATH"}), 400
    if not new_name:
        return jsonify({"error": "New name required", "code": "MISSING_NAME"}), 400

    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)

    if user.role != "admin":
        mtls_err = _require_mtls_for_protected(user)
        if mtls_err:
            return mtls_err
        parent = str(Path(path).parent)
        check_path = "/" if parent == "." else "/" + parent
        if not user_has_access(user, check_path, require_write=True):
            return jsonify({"error": "Write access denied", "code": "WRITE_ACCESS_DENIED"}), 403

    target_path = resolve_file_path(path)
    if not target_path or not target_path.exists():
        return jsonify({"error": "File not found", "code": "FILE_NOT_FOUND"}), 404

    safe_name = secure_filename(new_name)
    if not safe_name:
        return jsonify({"error": "Invalid file name", "code": "INVALID_NAME"}), 400

    new_path = target_path.parent / safe_name
    if new_path.exists():
        return jsonify({"error": "A file with that name already exists", "code": "NAME_EXISTS"}), 409

    # Ensure new path stays within storage
    storage_base = Path(CONFIG["STORAGE_PATH"]).resolve() / "files"
    if not str(new_path.resolve()).startswith(str(storage_base)):
        return jsonify({"error": "Invalid path", "code": "INVALID_PATH"}), 400

    try:
        target_path.rename(new_path)
        parent_rel = str(Path(path).parent)
        new_rel = (parent_rel + "/" + safe_name).lstrip("/").lstrip(".")
        if new_rel.startswith("/"):
            new_rel = new_rel[1:]
        log_audit(
            "file.rename",
            target_type="file",
            target_id=path,
            description=f"Renamed {path} to {new_rel}",
        )
        return jsonify({"success": True, "newPath": new_rel, "newName": safe_name}), 200
    except Exception as e:
        return jsonify({"error": str(e), "code": "RENAME_ERROR"}), 500


@app.route("/api/v1/files/move", methods=["POST"])
@auth.require_auth()
def api_move_file():
    """Move a file or directory to a new location (requires authentication)."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required", "code": "MISSING_BODY"}), 400

    src_path = data.get("srcPath", "").strip().lstrip("/")
    dest_dir = data.get("destDir", "").strip().lstrip("/")

    if not src_path:
        return jsonify({"error": "Source path required", "code": "MISSING_SRC"}), 400

    token = auth.get_token_from_request()
    user = auth.get_user_from_token(token)

    if user.role != "admin":
        mtls_err = _require_mtls_for_protected(user)
        if mtls_err:
            return mtls_err
        # Need write access on both source parent and destination
        src_parent = str(Path(src_path).parent)
        src_check = "/" if src_parent == "." else "/" + src_parent
        dest_check = "/" + dest_dir if dest_dir else "/"
        if not user_has_access(user, src_check, require_write=True):
            return jsonify({"error": "Write access denied on source", "code": "WRITE_ACCESS_DENIED"}), 403
        if not user_has_access(user, dest_check, require_write=True):
            return jsonify({"error": "Write access denied on destination", "code": "WRITE_ACCESS_DENIED"}), 403

    source = resolve_file_path(src_path)
    if not source or not source.exists():
        return jsonify({"error": "Source not found", "code": "FILE_NOT_FOUND"}), 404

    storage_base = Path(CONFIG["STORAGE_PATH"]).resolve() / "files"
    dest_parent = (storage_base / dest_dir).resolve() if dest_dir else storage_base

    # Guard against directory traversal
    if not str(dest_parent).startswith(str(storage_base)):
        return jsonify({"error": "Invalid destination", "code": "INVALID_PATH"}), 400

    if not dest_parent.exists() or not dest_parent.is_dir():
        return jsonify({"error": "Destination directory not found", "code": "DEST_NOT_FOUND"}), 404

    new_location = dest_parent / source.name
    if new_location.exists():
        return jsonify({"error": "An item with that name already exists in the destination", "code": "NAME_EXISTS"}), 409

    # Prevent moving a directory into itself
    if source.is_dir() and str(new_location.resolve()).startswith(str(source.resolve())):
        return jsonify({"error": "Cannot move a directory into itself", "code": "INVALID_MOVE"}), 400

    try:
        import shutil
        shutil.move(str(source), str(new_location))
        new_rel = str(Path(dest_dir) / source.name) if dest_dir else source.name
        log_audit(
            "file.move",
            target_type="file",
            target_id=src_path,
            description=f"Moved {src_path} to {new_rel}",
        )
        return jsonify({"success": True, "newPath": new_rel}), 200
    except Exception as e:
        return jsonify({"error": str(e), "code": "MOVE_ERROR"}), 500


@app.route("/api/v1/stats/dashboard", methods=["GET"])
@auth.require_admin()
def api_get_dashboard_stats():
    """Get dashboard statistics (admin only)."""
    from models import SystemSettings

    # Count users
    user_count = User.query.filter_by(role="user").count()

    # Count files and folders in pages subdirectory
    file_count = 0
    folder_count = 0
    total_size = 0

    files_path = Path(CONFIG["STORAGE_PATH"]) / "files"
    if files_path.exists():
        try:
            for item in files_path.rglob("*"):
                if item.is_file():
                    file_count += 1
                    total_size += item.stat().st_size
                elif item.is_dir():
                    folder_count += 1
        except Exception:
            pass

    # Get system settings
    settings = SystemSettings.query.first()

    return jsonify(
        {
            "userCount": user_count,
            "fileCount": file_count,
            "folderCount": folder_count,
            "totalSize": total_size,
            "tlsEnabled": settings.tls_enabled if settings else True,
        }
    ), 200


# =============================================================================
# Audit Log Endpoints (admin only)
# =============================================================================


@app.route("/api/v1/audit-logs", methods=["GET"])
@auth.require_admin()
def api_get_audit_logs():
    """Query audit logs with filtering and pagination (admin only)."""
    page = request.args.get("page", 1, type=int)
    limit = min(request.args.get("limit", 100, type=int), 500)
    action = request.args.get("action", "").strip()
    user_email = request.args.get("user_email", "").strip()
    status = request.args.get("status", "").strip()
    since = request.args.get("since", "").strip()
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    query = AuditLog.query

    # Category shortcut filters
    if category == "files":
        query = query.filter(AuditLog.action.like("file.%"))
    elif category == "security":
        query = query.filter(
            db.or_(
                AuditLog.action.like("auth.%"),
                AuditLog.action.like("cert.%"),
                AuditLog.action.like("permission.%"),
            )
        )
    elif action:
        query = query.filter(AuditLog.action.like(f"{action}%"))

    if user_email:
        query = query.filter(AuditLog.user_email.ilike(f"%{user_email}%"))

    if status in ("success", "failure"):
        query = query.filter(AuditLog.status == status)

    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00").replace("+00:00", ""))
            query = query.filter(AuditLog.timestamp > since_dt)
        except (ValueError, TypeError):
            pass

    if search:
        query = query.filter(AuditLog.description.ilike(f"%{search}%"))

    total = query.count()
    logs = query.order_by(AuditLog.timestamp.desc()).offset((page - 1) * limit).limit(limit).all()

    return jsonify(
        {
            "logs": [log.to_dict() for log in logs],
            "total": total,
            "page": page,
            "limit": limit,
        }
    ), 200


@app.route("/api/v1/audit-logs/stats", methods=["GET"])
@auth.require_admin()
def api_get_audit_log_stats():
    """Get audit log statistics (admin only)."""
    from sqlalchemy import func

    total = AuditLog.query.count()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today = AuditLog.query.filter(AuditLog.timestamp >= today_start).count()

    failed_auth_today = AuditLog.query.filter(
        AuditLog.timestamp >= today_start,
        AuditLog.action == "auth.login_failed",
    ).count()

    active_users_today = (
        db.session.query(func.count(func.distinct(AuditLog.user_id)))
        .filter(AuditLog.timestamp >= today_start, AuditLog.user_id.isnot(None))
        .scalar()
    ) or 0

    return jsonify(
        {
            "total": total,
            "today": today,
            "failedAuthToday": failed_auth_today,
            "activeUsersToday": active_users_today,
        }
    ), 200


# =============================================================================
# System / Docker Log Endpoints (admin only)
# =============================================================================


@app.route("/api/v1/system/logs", methods=["GET"])
@auth.require_admin()
def api_get_system_logs():
    """Stream Docker container logs (admin only).

    Requires the Docker socket to be mounted into the backend container.
    """
    container_name = request.args.get("container", "backend").strip()
    tail = min(request.args.get("tail", 200, type=int), 1000)
    since_param = request.args.get("since", "").strip()

    allowed_containers = {
        "backend": "terracrate-backend",
        "frontend": "terracrate-frontend",
    }
    docker_name = allowed_containers.get(container_name)
    if not docker_name:
        return jsonify({"error": "Invalid container name", "code": "INVALID_CONTAINER"}), 400

    try:
        import docker

        client = docker.from_env()
        container = client.containers.get(docker_name)

        kwargs = {"tail": tail, "timestamps": True, "stream": False}
        if since_param:
            try:
                kwargs["since"] = datetime.fromisoformat(since_param.replace("Z", "+00:00").replace("+00:00", ""))
            except (ValueError, TypeError):
                pass

        raw_logs = container.logs(**kwargs)
        lines = raw_logs.decode("utf-8", errors="replace").strip().splitlines()

        parsed = []
        for line in lines:
            # Docker timestamp format: 2026-04-06T14:23:01.123456789Z <message>
            timestamp = ""
            message = line
            if len(line) > 30 and line[4] == "-" and "T" in line[:25]:
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    timestamp = parts[0]
                    message = parts[1]

            parsed.append({"timestamp": timestamp, "line": message})

        return jsonify({"logs": parsed, "container": docker_name, "available": True}), 200

    except ImportError:
        return jsonify(
            {
                "logs": [],
                "container": docker_name,
                "available": False,
                "error": "Docker SDK not installed. Add 'docker' to requirements.txt.",
            }
        ), 200
    except Exception as e:
        error_msg = str(e)
        if "FileNotFoundError" in error_msg or "ConnectionError" in error_msg or "Error while fetching" in error_msg:
            return jsonify(
                {
                    "logs": [],
                    "container": docker_name,
                    "available": False,
                    "error": "Docker socket not available. Mount /var/run/docker.sock to enable system logs.",
                }
            ), 200
        return jsonify({"logs": [], "container": docker_name, "available": False, "error": f"Failed to fetch logs: {error_msg}"}), 500


# =============================================================================
# Legacy HTML Endpoints (for backward compatibility)
# =============================================================================


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin login - supports PIN (first-time) or email/password."""
    if request.method == "POST":
        pin = request.form.get("pin")
        email = request.form.get("email")
        password = request.form.get("password")

        admin_user = None

        # Try PIN authentication (for first-time login with is_default_pin=True)
        if pin:
            admin_user = auth.validate_admin_pin(pin)
            if admin_user:
                # PIN is valid - generate session and check if first-time setup needed
                admin_token = auth.generate_session_token(admin_user)

                if admin_user.is_default_pin:
                    # First-time login - redirect to setup
                    response = redirect("/admin/first-setup")
                else:
                    # Normal login
                    response = redirect("/admin")

                response.set_cookie(
                    "admin_token",
                    admin_token,
                    httponly=True,
                    secure=True,
                    samesite="Strict",
                    max_age=2 * 3600,  # 2 hours
                )
                return response

        # Try email/password authentication
        if email and password:
            admin_user = auth.authenticate_user(email, password)
            if admin_user and admin_user.role == "admin":
                # Generate session token
                admin_token = auth.generate_session_token(admin_user)

                # Set cookie and redirect to admin dashboard
                response = redirect("/admin")
                response.set_cookie(
                    "admin_token",
                    admin_token,
                    httponly=True,
                    secure=True,
                    samesite="Strict",
                    max_age=2 * 3600,  # 2 hours
                )
                return response

        # Invalid credentials
        return render_admin_login_page(error="Invalid credentials")

    # GET request - show login form
    return render_admin_login_page()


def render_admin_login_page(error=None):
    """Render admin login page."""
    return render_template("admin_login.html", service_name=CONFIG["SERVICE_NAME"], error=error)


@app.route("/admin/first-setup", methods=["GET", "POST"])
@auth.require_admin()
def admin_first_setup():
    """First-time setup for admin - set email and new password."""
    # Get user from token
    token = auth.get_admin_token_from_request()
    admin_user = auth.get_user_from_token(token)

    if not admin_user or not admin_user.is_default_pin:
        # Already set up or invalid token
        return redirect("/admin")

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        # Validation
        errors = []
        if not email or "@" not in email:
            errors.append("Valid email is required")
        if not password:
            errors.append("Password is required")
        if password != confirm_password:
            errors.append("Passwords do not match")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters")

        # Check if email is already taken by another user
        existing_user = User.query.filter_by(email=email).first()
        if existing_user and existing_user.id != admin_user.id:
            errors.append("Email already in use")

        if errors:
            return render_template("first_setup.html", service_name=CONFIG["SERVICE_NAME"], errors=errors, email=email)

        # Update admin user
        admin_user.email = email
        admin_user.password_hash = auth.hash_password(password)
        admin_user.is_default_pin = False
        db.session.commit()

        return redirect("/admin")

    # GET request - show setup form
    return render_template("first_setup.html", service_name=CONFIG["SERVICE_NAME"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration."""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        # Validation
        errors = []
        if not email or "@" not in email:
            errors.append("Valid email is required")
        if not password:
            errors.append("Password is required")
        if password != confirm_password:
            errors.append("Passwords do not match")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters")

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            errors.append("Email already registered")

        if errors:
            return render_template("register.html", service_name=CONFIG["SERVICE_NAME"], errors=errors, email=email)

        # Create new user
        new_user = User(email=email, password_hash=auth.hash_password(password), role="user", is_default_pin=False)
        db.session.add(new_user)
        db.session.commit()

        # Auto-login after registration
        user_token = auth.generate_session_token(new_user)
        response = redirect("/")
        response.set_cookie(
            "auth_token",
            user_token,
            httponly=True,
            secure=True,
            samesite="Strict",
            max_age=CONFIG["TOKEN_EXPIRY_HOURS"] * 3600,
        )
        return response

    # GET request - show registration form
    return render_template("register.html", service_name=CONFIG["SERVICE_NAME"])


@app.route("/login", methods=["GET", "POST"])
def login():
    """User login."""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        # Authenticate
        user = auth.authenticate_user(email, password)

        if not user:
            return render_template(
                "login.html", service_name=CONFIG["SERVICE_NAME"], error="Invalid email or password", email=email
            )

        # Don't allow admin to login via regular login page
        if user.role == "admin":
            return render_template(
                "login.html",
                service_name=CONFIG["SERVICE_NAME"],
                error="Admin users must use /admin/login",
                email=email,
            )

        # Generate session token
        user_token = auth.generate_session_token(user)
        response = redirect("/")
        response.set_cookie(
            "auth_token",
            user_token,
            httponly=True,
            secure=True,
            samesite="Strict",
            max_age=CONFIG["TOKEN_EXPIRY_HOURS"] * 3600,
        )
        return response

    # GET request - show login form
    return render_template("login.html", service_name=CONFIG["SERVICE_NAME"])


@app.route("/logout", methods=["GET", "POST"])
def logout():
    """Logout user."""
    response = redirect("/login")
    response.set_cookie("auth_token", "", expires=0)
    response.set_cookie("admin_token", "", expires=0)
    return response


@app.route("/auth")
def authenticate():
    """Guest authentication endpoint - sets cookie and redirects to main page."""
    token = request.args.get("token")

    if not token:
        return "No token provided", 401

    if not auth.validate_token(token):
        return "Invalid or expired token", 401

    # Set secure HttpOnly cookie
    response = redirect("/")
    response.set_cookie(
        "auth_token", token, httponly=True, secure=True, samesite="Strict", max_age=CONFIG["TOKEN_EXPIRY_HOURS"] * 3600
    )

    return response


@app.route("/admin")
@auth.require_admin()
def admin_dashboard():
    """Admin dashboard - user management and settings."""
    # TODO: Create new admin dashboard for user management
    # For now, show simple welcome message
    token = auth.get_admin_token_from_request()
    admin_user = auth.get_user_from_token(token)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Dashboard - {CONFIG["SERVICE_NAME"]}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }}
            .container {{
                background: white;
                border-radius: 12px;
                padding: 40px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{ color: #333; }}
            .info {{ margin: 20px 0; color: #666; }}
            a {{ color: #007bff; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>👨‍💼 Admin Dashboard</h1>
            <p class="info">Welcome, {admin_user.email if admin_user else "Admin"}!</p>
            <p class="info">
                <a href="/">Browse Files</a> |
                <a href="/logout">Logout</a>
            </p>
            <p class="info" style="margin-top: 40px; color: #999;">
                TODO: User management features coming soon
            </p>
        </div>
    </body>
    </html>
    """


# TODO: Refactor token management for user-specific tokens
# @app.route('/admin/generate-token', methods=['POST'])
# @auth.require_admin()
# def admin_generate_token():
#     """Generate a new guest token."""
#     token = auth.generate_guest_token(read_only=not CONFIG['ENABLE_UPLOADS'])
#     return redirect('/admin')


# @app.route('/admin/revoke-token/<token_id>', methods=['POST'])
# @auth.require_admin()
# def admin_revoke_token(token_id):
#     """Revoke a guest token."""
#     auth.revoke_guest_token(token_id)
#     return redirect('/admin')


# def render_admin_dashboard():
#     """Render the admin dashboard with active tokens."""
# def render_admin_dashboard():
#     """Render the admin dashboard with active tokens."""
#     active_tokens = auth.get_active_guest_tokens()
#     server_url = get_server_url()
#
#     # Generate QR codes for each token
#     token_items = []
#     for token_info in active_tokens:
#         qr_gen = QRGenerator(server_url, token_info['token'])
#         qr_image = qr_gen.generate_qr_base64()
#         token_items.append({
#             'id': token_info['id'],
#             'qr_image': qr_image,
#             'created': token_info['created'],
#             'expires': token_info['expires'],
#         })
#
#     return render_template(
#         'admin_dashboard.html',
#         service_name=CONFIG['SERVICE_NAME'],
#         token_items=token_items
#     )


@app.route("/")
def index():
    """Main page - file browser for authenticated users."""
    token = auth.get_token_from_request()

    if not token or not auth.validate_token(token):
        # No valid token, redirect to login
        return redirect("/login")

    # Valid token, show file browser (accessible to all authenticated users)
    return render_file_browser()


def render_file_browser():
    """Render the file browser interface."""
    path = request.args.get("path", "")
    files = get_file_list(path)

    # Add formatted size to each file
    for file in files:
        file["size_formatted"] = format_size(file["size"])

    # Get parent path
    parent_path = os.path.dirname(path) if path else ""

    return render_template(
        "file_browser.html",
        service_name=CONFIG["SERVICE_NAME"],
        enable_uploads=CONFIG["ENABLE_UPLOADS"],
        current_path=path,
        parent_path=parent_path,
        files=files,
    )


def format_size(size):
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


@app.route("/download/<path:filepath>")
@auth.require_auth("read")
def download_file(filepath):
    """Download a file with chunked streaming for mobile compatibility."""
    full_path = os.path.join(CONFIG["STORAGE_PATH"], filepath)

    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return jsonify({"error": "File not found"}), 404

    try:
        # Use send_file with conditional response and chunked streaming
        # This enables range requests for mobile browsers and resumable downloads
        return send_file(
            full_path,
            as_attachment=True,
            conditional=True,  # Enable If-Modified-Since and range requests
            max_age=0,  # No caching for private files
            download_name=os.path.basename(filepath),  # Clean filename
        )
    except Exception as e:
        print(f"Error serving file {filepath}: {e}")
        return jsonify({"error": "Error downloading file"}), 500


@app.route("/upload", methods=["POST"])
@auth.require_auth("write")
def upload_file():
    """Upload a file."""
    if not CONFIG["ENABLE_UPLOADS"]:
        return jsonify({"error": "Uploads disabled"}), 403

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    path = request.form.get("path", "")

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    filename = secure_filename(file.filename)
    full_path = os.path.join(CONFIG["STORAGE_PATH"], path, filename)

    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    file.save(full_path)

    token = auth.get_token_from_request()
    return redirect(f"/?path={path}&token={token}")


# TODO: Refactor QR code generation for user-specific tokens
# @app.route('/qr')
# def qr_code():
#     """Generate QR code for current access."""
#     token = request.args.get('token', '')
#     if not token:
#         token = auth.generate_guest_token()
#
#     server_url = get_server_url()
#     qr_gen = QRGenerator(server_url, token)
#     qr_image = qr_gen.generate_qr_base64()
#
#     return jsonify({
#         'qr_image': qr_image,
#         'access_url': qr_gen.generate_access_url(),
#         'token': token
#     })


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "version": "2.0", "service": CONFIG["SERVICE_NAME"]})


def create_default_admin(hostname, pin):
    """Create the default admin user with an email derived from the mDNS hostname.

    Returns the created User, or None if an admin already exists.
    """
    admin_user = User.query.filter_by(role="admin").first()
    if admin_user:
        return None
    default_admin_email = f"admin@{hostname}.local"
    default_admin = User(
        email=default_admin_email,
        password_hash=auth.hash_password(pin),
        role="admin",
        is_default_pin=True,
    )
    db.session.add(default_admin)
    db.session.commit()
    print(f"✅ Default admin user created ({default_admin_email})")
    print(f"   Password: {pin} (must be changed on first login)")
    return default_admin


# ── Certificate Expiry Background Task ───────────────────────────────────────

CERT_EXPIRY_CHECK_DAYS = int(os.getenv("CERT_EXPIRY_CHECK_DAYS", "7"))
CERT_EXPIRY_CHECK_INTERVAL_HOURS = int(os.getenv("CERT_EXPIRY_CHECK_INTERVAL_HOURS", "24"))


def _check_expiring_certs():
    """Revoke certs nearing expiry and notify users."""
    import logging

    logger = logging.getLogger(__name__)

    with app.app_context():
        threshold = datetime.utcnow() + timedelta(days=CERT_EXPIRY_CHECK_DAYS)
        expiring = User.query.filter(
            User.cert_expires_at <= threshold,
            User.cert_revoked == False,  # noqa: E712
            User.cert_serial_number.isnot(None),
        ).all()

        if not expiring:
            return

        from models import SystemSettings

        settings = SystemSettings.query.first()

        for user in expiring:
            logger.info("Auto-revoking expiring cert for %s (expires %s)", user.email, user.cert_expires_at)
            _revoke_user_cert(user, "expiry_approaching")
            if settings and settings.smtp_enabled:
                send_revocation_email(
                    user.email,
                    settings.device_name or "TerraCrate",
                    settings,
                    reason="Your certificate is expiring soon.",
                )


def _start_cert_expiry_checker():
    """Start a daemon thread that periodically checks for expiring certs."""
    import threading
    import time

    def _loop():
        interval = CERT_EXPIRY_CHECK_INTERVAL_HOURS * 3600
        while True:
            try:
                _check_expiring_certs()
            except Exception:
                import logging

                logging.getLogger(__name__).error("Cert expiry check failed", exc_info=True)
            time.sleep(interval)

    t = threading.Thread(target=_loop, daemon=True, name="cert-expiry-checker")
    t.start()


def main():
    """Main server entry point."""
    print("=" * 60)
    print(f"TerraCrate API v2 - {CONFIG['SERVICE_NAME']}")
    print("=" * 60)

    # Check certificates
    if not os.path.exists(CONFIG["CERT_PATH"]) or not os.path.exists(CONFIG["KEY_PATH"]):
        print("ERROR: SSL certificates not found!")
        print("   Certificate path: " + CONFIG["CERT_PATH"])
        print("   Key path: " + CONFIG["KEY_PATH"])
        print("   Run: python utils/generate_certs.py")
        sys.exit(1)

    # Ensure database directory exists
    db_path = Path(CONFIG["DATABASE_URI"].replace("sqlite:///", ""))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Initialize database tables
    with app.app_context():
        db.create_all()

        print("✅ Database initialized")

        # Ensure an empty CRL exists so nginx can start with ssl_crl
        from utils.generate_certs import generate_empty_crl

        crl_path = os.path.join(os.path.dirname(CONFIG["CERT_PATH"]), "crl.pem")
        generate_empty_crl(CONFIG["CERT_PATH"], CONFIG["KEY_PATH"], crl_path)

        # Create default system settings if not exists
        from models import SystemSettings

        if not SystemSettings.query.first():
            default_settings = SystemSettings(
                mode="open",
                auth_method="email+password",
                tls_enabled=True,
                https_port=CONFIG["PORT"],
                device_name=CONFIG["SERVICE_NAME"],
            )
            db.session.add(default_settings)
            db.session.commit()
            print("✅ Default system settings created")

        # Create default admin user if no admin exists
        create_default_admin(CONFIG["MDNS_HOSTNAME"], CONFIG["ADMIN_PIN"])

    # Generate initial access token
    token = auth.generate_guest_token(read_only=not CONFIG["ENABLE_UPLOADS"])

    # Start certificate expiry checker background thread
    _start_cert_expiry_checker()

    # Setup mDNS advertising
    mdns = MDNSAdvertiser(
        service_name=CONFIG["SERVICE_NAME"],
        port=CONFIG["PORT"],
        hostname=CONFIG["MDNS_HOSTNAME"],
        service_type="_https._tcp",
    )
    mdns.advertise()
    # Setup SSL context
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(CONFIG["CERT_PATH"], CONFIG["KEY_PATH"])

    # Display access information
    server_url = get_server_url()
    QRGenerator(server_url, token)

    print()
    print("✅ Server started successfully!")
    print()
    print(f"📍 Server URL: {server_url}")
    print(f"🔑 Access Token: {token}")
    print()
    # Run server with mobile-friendly settings
    try:
        run_simple(
            CONFIG["HOST"],
            CONFIG["PORT"],
            app,
            ssl_context=ssl_context,
            use_reloader=False,
            use_debugger=False,
            threaded=True,  # Handle multiple requests concurrently
            request_handler=None,  # Use default handler with keep-alive support
        )
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down server...")
        mdns.stop()
        print("✅ Server stopped")


if __name__ == "__main__":
    main()
