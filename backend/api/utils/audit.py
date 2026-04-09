"""
Audit logging utility for TerraCrate.

Provides a single ``log_audit()`` helper that writes to the ``audit_logs``
table.  Failures are silently caught so that audit logging never breaks the
main request flow.
"""

import json
import logging

from flask import has_request_context, request

from models import AuditLog, db

logger = logging.getLogger(__name__)


def log_audit(
    action: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    description: str | None = None,
    status: str = "success",
    metadata: dict | None = None,
    user_id: int | None = None,
    user_email: str | None = None,
):
    """Record an audit log entry.

    Parameters
    ----------
    action : str
        Dotted action identifier, e.g. ``"auth.login"``, ``"file.upload"``.
    target_type : str, optional
        Kind of entity acted upon (``"user"``, ``"file"``, ``"group"``, …).
    target_id : str, optional
        Identifier of the target (user id, file path, group id, …).
    description : str, optional
        Human-readable summary of what happened.
    status : str
        ``"success"`` (default) or ``"failure"``.
    metadata : dict, optional
        Extra context serialised as JSON (old/new values, sizes, …).
    user_id : int, optional
        Override – pulled from ``request.user`` when omitted.
    user_email : str, optional
        Override – pulled from ``request.user`` when omitted.
    """
    try:
        # Auto-detect user context from Flask request
        if has_request_context():
            req_user = getattr(request, "user", None)
            if req_user and user_id is None:
                user_id = req_user.get("user_id")
            if req_user and user_email is None:
                user_email = req_user.get("email")

        # Capture IP address
        ip_address = None
        if has_request_context():
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)

        entry = AuditLog(
            user_id=user_id,
            user_email=user_email,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            description=description,
            ip_address=ip_address,
            status=status,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        logger.debug("Failed to write audit log entry", exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass
