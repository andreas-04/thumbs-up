"""
Email notification utility for ThumbsUp.
Uses Python's built-in smtplib — no extra dependencies required.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _send_email(settings, to_email, subject, body_html, body_text):
    """Send an email via SMTP using the provided SystemSettings object.

    Returns (success: bool, error: str | None).
    """
    if not settings.smtp_enabled:
        return False, "SMTP is not enabled"

    host = (settings.smtp_host or "").strip()
    if not host:
        return False, "SMTP host is not configured"

    from_email = (settings.smtp_from_email or "").strip() or (settings.smtp_username or "").strip()
    if not from_email:
        return False, "SMTP from-email is not configured"

    port = settings.smtp_port or 587
    username = (settings.smtp_username or "").strip()
    password = settings.smtp_password or ""
    use_tls = settings.smtp_use_tls if settings.smtp_use_tls is not None else True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        if use_tls:
            server = smtplib.SMTP(host, port, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(host, port, timeout=15)

        if username:
            server.login(username, password)

        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        logger.info("Email sent to %s: %s", to_email, subject)
        return True, None
    except Exception as exc:
        error_msg = f"Failed to send email to {to_email}: {exc}"
        logger.error(error_msg)
        return False, error_msg


def send_approval_email(user_email, device_name, settings):
    """Notify a user that their account has been approved for protected file access."""
    subject = f"Your account on {device_name} has been approved"
    body_text = (
        f"Good news! Your account ({user_email}) on {device_name} has been approved by an administrator.\n\n"
        f"You now have access to protected files. Log in with your existing credentials to get started.\n"
    )
    body_html = (
        f"<h2>Account Approved</h2>"
        f"<p>Good news! Your account (<strong>{user_email}</strong>) on <strong>{device_name}</strong> "
        f"has been approved by an administrator.</p>"
        f"<p>You now have access to protected files. Log in with your existing credentials to get started.</p>"
    )
    return _send_email(settings, user_email, subject, body_html, body_text)


def send_invite_email(user_email, device_name, settings):
    """Notify a user that an account has been pre-created for them."""
    subject = f"You've been invited to {device_name}"
    body_text = (
        f"An account has been created for you on {device_name}.\n\n"
        f"To get started, visit the site and sign up with this email address: {user_email}\n"
        f"You will be able to set your own password during signup.\n"
    )
    body_html = (
        f"<h2>You're Invited</h2>"
        f"<p>An account has been created for you on <strong>{device_name}</strong>.</p>"
        f"<p>To get started, visit the site and sign up with this email address: "
        f"<strong>{user_email}</strong></p>"
        f"<p>You will be able to set your own password during signup.</p>"
    )
    return _send_email(settings, user_email, subject, body_html, body_text)
