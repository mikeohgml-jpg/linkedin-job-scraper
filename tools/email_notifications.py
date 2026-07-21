import smtplib
from email.message import EmailMessage
from pathlib import Path

RESEND_SMTP_HOST = "smtp.resend.com"
RESEND_SMTP_PORT = 465


def send_completion_email(
    job_count: int,
    keyword: str,
    scope_label: str,
    scope_value: str,
    filename: str,
    api_key: str,
    notify_email: str,
    from_email: str,
):
    """Send a completion email through Resend's SMTP relay."""
    if not (api_key and notify_email and from_email):
        print("  (Email notification skipped — RESEND_API_KEY / NOTIFY_EMAIL / FROM_EMAIL not configured)")
        return

    body = (
        f"Your LinkedIn scrape has completed!\n\n"
        f"  Keyword : {keyword}\n"
        f"  {scope_label}: {scope_value}\n"
        f"  Jobs    : {job_count}\n"
        f"  File    : {Path(filename).name}\n\n"
        f"Log in to the app to view and download your results."
    )

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = notify_email
    msg["Subject"] = f"LinkedIn Scrape Done: {job_count} '{keyword}' jobs in {scope_value}"
    msg.set_content(body)

    try:
        with smtplib.SMTP_SSL(RESEND_SMTP_HOST, RESEND_SMTP_PORT, timeout=15) as server:
            server.login("resend", api_key)
            server.send_message(msg)
        print(f"  Email notification sent to {notify_email}")
    except smtplib.SMTPAuthenticationError as exc:
        print(f"  Email notification failed (auth error): {exc}")
    except Exception as exc:
        print(f"  Email notification failed ({type(exc).__name__}): {exc}")
