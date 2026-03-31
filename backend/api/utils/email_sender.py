"""
Email notification utility for ThumbsUp.
Uses Python's built-in smtplib — no extra dependencies required.
"""

import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.generate_certs import generate_client_p12

logger = logging.getLogger(__name__)


def _send_email(settings, to_email, subject, body_html, body_text, attachments=None):
    """Send an email via SMTP using the provided SystemSettings object.

    Args:
        settings: SystemSettings object with SMTP configuration
        to_email: Recipient email address
        subject: Email subject
        body_html: HTML body content
        body_text: Plain text body content
        attachments: Optional list of (filename, data_bytes) tuples

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

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    # Add text/html alternative body
    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(body_text, "plain"))
    body_part.attach(MIMEText(body_html, "html"))
    msg.attach(body_part)

    # Add file attachments
    for filename, data in attachments or []:
        part = MIMEApplication(data, Name=filename)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)

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


def send_approval_email(user_email, device_name, settings, ca_cert_path=None, ca_key_path=None):
    """Notify a user that their account has been approved for protected file access.

    When CA cert/key paths are provided, a client certificate is generated and
    attached to the email for mTLS authentication.
    """
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

    attachments = []
    cert_generated = False
    p12_password = None

    if ca_cert_path and ca_key_path:
        try:
            p12_bytes, p12_password = generate_client_p12(ca_cert_path, ca_key_path, user_email)
            attachments.append(("thumbsup-client.p12", p12_bytes))
            cert_generated = True
        except Exception as exc:
            logger.error("Failed to generate client cert for %s: %s", user_email, exc)

    if cert_generated:
        body_text += (
            "\nYour client certificate (.p12) for mTLS is attached.\n"
            f"Import password: {p12_password}\n"
            "Install it on your device to gain access to protected files.\n"
        )
        body_html += (
            "<p>Your client certificate (<code>.p12</code>) for mTLS is attached.</p>"
            f"<p><strong>Import password:</strong> <code>{p12_password}</code></p>"
            "<p>Install it on your device to gain access to protected files.</p>"
        )

    return _send_email(settings, user_email, subject, body_html, body_text, attachments=attachments)


def send_invite_email(user_email, device_name, settings, ca_cert_path=None, ca_key_path=None, p12_data=None):
    """Notify a user that an account has been pre-created for them.

    Args:
        p12_data: Optional pre-generated (p12_bytes, p12_password) tuple.
                  When provided, the cert is attached directly and the password
                  is included as the user's temporary login password.
                  When None but ca_cert_path/ca_key_path are given, a cert is
                  generated on the fly (legacy behaviour).
    """
    attachments = []
    cert_generated = False
    p12_password = None

    # Use pre-generated cert data if provided, otherwise generate on the fly
    if p12_data:
        p12_bytes, p12_password = p12_data
        attachments.append(("thumbsup-client.p12", p12_bytes))
        cert_generated = True
    elif ca_cert_path and ca_key_path:
        try:
            p12_bytes, p12_password = generate_client_p12(ca_cert_path, ca_key_path, user_email)
            attachments.append(("thumbsup-client.p12", p12_bytes))
            cert_generated = True
        except Exception as exc:
            logger.error("Failed to generate client cert for %s: %s", user_email, exc)

    subject = f"You've been invited to {device_name}"
    body_text = (
        f"An account has been created for you on {device_name}.\n\n"
        f"To get started, import the attached certificate on your device, "
        f"then log in with your email address: {user_email}\n"
    )
    body_html = (
        f"<h2>You're Invited</h2>"
        f"<p>An account has been created for you on <strong>{device_name}</strong>.</p>"
        f"<p>To get started, import the attached certificate on your device, "
        f"then log in with your email: <strong>{user_email}</strong></p>"
    )

    if cert_generated:
        body_text += (
            f"\nYour client certificate (.p12) for mTLS is attached.\n"
            f"Import password / temporary login password: {p12_password}\n"
            f"You will be asked to set a new password on first login.\n"
        )
        body_html += (
            "<p>Your client certificate (<code>.p12</code>) for mTLS is attached.</p>"
            f"<p><strong>Import password / temporary login password:</strong> <code>{p12_password}</code></p>"
            "<p>You will be asked to set a new password on first login.</p>"
        )
    else:
        body_text += (
            "\nYour temporary login password is: changeme\nYou will be asked to set a new password on first login.\n"
        )
        body_html += (
            "<p><strong>Temporary login password:</strong> <code>changeme</code></p>"
            "<p>You will be asked to set a new password on first login.</p>"
        )

    return _send_email(settings, user_email, subject, body_html, body_text, attachments=attachments)
