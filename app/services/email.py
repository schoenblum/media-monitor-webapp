"""Async email delivery via aiosmtplib.

Falls back to logging when SMTP is not configured or delivery fails.
Port 465 → implicit SSL (SMTP_SSL=True). Port 587 → STARTTLS (SMTP_SSL=False).
"""
import logging
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from uuid import UUID

import aiosmtplib

from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body_html: str, body_text: str | None = None) -> bool:
    """Send an email. Returns True on success, False on failure (also logs the content)."""
    settings = get_settings()

    logger.info(
        "Email to=%s subject=%r body_text=%r",
        to,
        subject,
        (body_text or body_html)[:500],
    )

    if not settings.SMTP_HOST or not settings.SMTP_FROM:
        logger.warning("SMTP not configured — email not delivered (see log above for content)")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to

    if body_text:
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            use_tls=settings.SMTP_SSL,
            start_tls=not settings.SMTP_SSL and settings.SMTP_PORT == 587,
        )
        logger.info("Email delivered to %s", to)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Email delivery failed to %s: %s", to, exc)
        return False


async def send_email_with_attachment(
    to: str,
    subject: str,
    body_html: str,
    attachment_bytes: bytes,
    attachment_filename: str,
    attachment_mime: tuple[str, str] = ("text", "csv"),
    body_text: str | None = None,
) -> bool:
    """Send an email carrying a single binary attachment (e.g. a CSV export)."""
    settings = get_settings()

    logger.info("Email (attachment) to=%s subject=%r file=%s", to, subject, attachment_filename)

    if not settings.SMTP_HOST or not settings.SMTP_FROM:
        logger.warning("SMTP not configured — attachment email to %s not delivered", to)
        return False

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to

    alt = MIMEMultipart("alternative")
    if body_text:
        alt.attach(MIMEText(body_text, "plain", "utf-8"))
    alt.attach(MIMEText(body_html, "html", "utf-8"))
    msg.attach(alt)

    maintype, subtype = attachment_mime
    part = MIMEApplication(attachment_bytes, _subtype=subtype)
    part.add_header("Content-Disposition", "attachment", filename=attachment_filename)
    msg.attach(part)

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            use_tls=settings.SMTP_SSL,
            start_tls=not settings.SMTP_SSL and settings.SMTP_PORT == 587,
        )
        logger.info("Attachment email delivered to %s", to)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Attachment email delivery failed to %s: %s", to, exc)
        return False


async def send_run_notification(
    to: str,
    search_name: str,
    run_id: UUID,
    hit_count: int,
    samples: list[tuple[str, str]],
) -> bool:
    """Notify a recipient that an unattended run found new hits."""
    settings = get_settings()
    run_url = f"{settings.BASE_URL.rstrip('/')}/runs/{run_id}"
    plural = "hit" if hit_count == 1 else "hits"
    subject = f"[Media Monitor] {hit_count} new {plural} — {search_name}"

    text_lines = [
        f'Your search "{search_name}" found {hit_count} new {plural}.',
        "",
        f"Review and export them here: {run_url}",
    ]
    if samples:
        text_lines += ["", "Most recent:"]
        text_lines += [f"  • {title}\n    {url}" for title, url in samples]
    body_text = "\n".join(text_lines) + "\n\nContact: mm@schenz.eu"

    sample_html = "".join(
        f'<li style="margin-bottom:8px"><a href="{escape(url)}">{escape(title)}</a></li>'
        for title, url in samples
    )
    body_html = f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:560px;margin:0 auto;padding:24px">
  <h2 style="color:#1e40af">Media Monitor — new {escape(plural)}</h2>
  <p>Your search <strong>{escape(search_name)}</strong> found
     <strong>{hit_count}</strong> new {escape(plural)}.</p>
  <p><a href="{escape(run_url)}"
        style="display:inline-block;background:#1e40af;color:#fff;padding:8px 16px;border-radius:6px;text-decoration:none">
     Review &amp; export</a></p>
  {f'<p style="color:#555;font-size:0.9em;margin-top:20px">Most recent:</p><ul style="padding-left:18px">{sample_html}</ul>' if sample_html else ''}
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="font-size:0.8em;color:#94a3b8">Media Monitor · <a href="mailto:mm@schenz.eu">mm@schenz.eu</a></p>
</body>
</html>"""
    return await send_email(to, subject, body_html, body_text)


async def send_export_email(
    to: str,
    csv_bytes: bytes,
    filename: str,
    hit_count: int,
) -> bool:
    """Email a CSV export of selected hits as an attachment."""
    plural = "hit" if hit_count == 1 else "hits"
    subject = f"[Media Monitor] Export — {hit_count} {plural}"
    body_text = (
        f"Attached is your Media Monitor export ({hit_count} selected {plural}).\n\n"
        f"File: {filename}\n\nContact: mm@schenz.eu"
    )
    body_html = f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px">
  <h2 style="color:#1e40af">Media Monitor — export</h2>
  <p>Attached is your export of <strong>{hit_count}</strong> selected {escape(plural)}
     (<code>{escape(filename)}</code>).</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="font-size:0.8em;color:#94a3b8">Media Monitor · <a href="mailto:mm@schenz.eu">mm@schenz.eu</a></p>
</body>
</html>"""
    return await send_email_with_attachment(
        to, subject, body_html, csv_bytes, filename, ("text", "csv"), body_text
    )


async def send_welcome_email(to: str, initial_password: str, app_url: str) -> bool:
    subject = "[Media Monitor] Your account is ready — mm.schenz.eu"
    body_text = (
        f"Your Media Monitor account has been created.\n\n"
        f"Login: {app_url}/login\n"
        f"Email: {to}\n"
        f"Temporary password: {initial_password}\n\n"
        f"You will be asked to change your password on first login.\n\n"
        f"Contact: mm@schenz.eu"
    )
    body_html = f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px">
  <h2 style="color:#1e40af">Media Monitor — Account ready</h2>
  <p>Your account has been created. Use the credentials below to sign in:</p>
  <table style="border-collapse:collapse;width:100%">
    <tr><td style="padding:6px 0;color:#555">Login URL</td>
        <td style="padding:6px 0"><a href="{app_url}/login">{app_url}/login</a></td></tr>
    <tr><td style="padding:6px 0;color:#555">Email</td>
        <td style="padding:6px 0">{to}</td></tr>
    <tr><td style="padding:6px 0;color:#555">Temporary password</td>
        <td style="padding:6px 0"><code style="background:#f1f5f9;padding:2px 6px;border-radius:4px">{initial_password}</code></td></tr>
  </table>
  <p style="margin-top:16px;font-size:0.9em;color:#555">
    You will be asked to choose a new password on first login.
  </p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="font-size:0.8em;color:#94a3b8">Media Monitor · <a href="mailto:mm@schenz.eu">mm@schenz.eu</a></p>
</body>
</html>"""
    return await send_email(to, subject, body_html, body_text)
