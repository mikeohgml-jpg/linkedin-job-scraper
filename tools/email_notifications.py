import json
import urllib.error
import urllib.request
from pathlib import Path


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
    """Send a completion email through Brevo's HTTP API."""
    if not (api_key and notify_email and from_email):
        print("  (Email notification skipped — BREVO_API_KEY / NOTIFY_EMAIL / FROM_EMAIL not configured)")
        return

    body = (
        f"Your LinkedIn scrape has completed!\n\n"
        f"  Keyword : {keyword}\n"
        f"  {scope_label}: {scope_value}\n"
        f"  Jobs    : {job_count}\n"
        f"  File    : {Path(filename).name}\n\n"
        f"Log in to the app to view and download your results."
    )
    payload = json.dumps(
        {
            "sender":      {"name": "LinkedIn Scraper", "email": from_email},
            "to":          [{"email": notify_email}],
            "subject":     f"LinkedIn Scrape Done: {job_count} '{keyword}' jobs in {scope_value}",
            "textContent": body,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=payload,
        headers={
            "api-key":      api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status in (200, 201, 202):
                print(f"  Email notification sent to {notify_email}")
            else:
                print(f"  Email notification failed: HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        print(f"  Email notification failed ({type(exc).__name__}): {exc}")
        try:
            response_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            response_body = ""
        if response_body:
            print(f"  Brevo response: {response_body}")
    except Exception as exc:
        print(f"  Email notification failed ({type(exc).__name__}): {exc}")
