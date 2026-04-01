"""Email delivery for the daily digest."""

import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src.config import Settings

logger = logging.getLogger(__name__)


def deliver_email(
    md_path: Path, json_path: Path, settings: Settings
) -> None:
    """Send the digest via email with the JSON file as attachment."""
    if settings.smtp is None:
        logger.error(
            "Email delivery requested but SMTP is not configured. "
            "Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in .env"
        )
        return

    smtp = settings.smtp
    if not smtp.recipients:
        logger.error("No email recipients configured (EMAIL_TO in .env)")
        return

    # Build email
    msg = MIMEMultipart()
    msg["Subject"] = f"Digest Diário — {md_path.stem.replace('digest-', '')}"
    msg["From"] = smtp.user
    msg["To"] = ", ".join(smtp.recipients)

    # Markdown content as plain text body
    md_content = md_path.read_text(encoding="utf-8")
    msg.attach(MIMEText(md_content, "plain", "utf-8"))

    # JSON as attachment
    json_content = json_path.read_bytes()
    attachment = MIMEApplication(json_content, Name=json_path.name)
    attachment["Content-Disposition"] = f'attachment; filename="{json_path.name}"'
    msg.attach(attachment)

    # Send
    try:
        with smtplib.SMTP(smtp.host, smtp.port, timeout=30) as server:
            server.starttls()
            server.login(smtp.user, smtp.password)
            server.sendmail(smtp.user, smtp.recipients, msg.as_string())
        logger.info("Digest emailed to %s", ", ".join(smtp.recipients))
    except smtplib.SMTPException as e:
        logger.error("Failed to send email: %s", e)
