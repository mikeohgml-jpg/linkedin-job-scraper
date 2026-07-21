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
    app_url: str = "",
):
    """Send a completion email through Brevo's HTTP API."""
    if not (api_key and notify_email and from_email):
        print("  (Email notification skipped — BREVO_API_KEY / NOTIFY_EMAIL / FROM_EMAIL not configured)")
        return

    fname = Path(filename).name
    app_link = app_url.rstrip("/") if app_url else ""

    text_body = (
        f"Your LinkedIn scrape has completed!\n\n"
        f"  Keyword : {keyword}\n"
        f"  {scope_label}: {scope_value}\n"
        f"  Jobs    : {job_count}\n"
        f"  File    : {fname}\n\n"
        f"Log in to the app to view and download your results."
        + (f"\n{app_link}" if app_link else "")
    )

    button_html = (
        f'<p><a href="{app_link}" '
        f'style="background:#0077b5;color:#fff;padding:10px 20px;'
        f'border-radius:5px;text-decoration:none;font-weight:bold;">'
        f'Open App &amp; Download Results</a></p>'
        if app_link else
        "<p>Log in to the app to view and download your results.</p>"
    )

    html_body = f"""
<div style="font-family:Arial,sans-serif;max-width:500px">
  <h2 style="color:#0077b5">LinkedIn Scrape Completed ✓</h2>
  <table style="border-collapse:collapse;width:100%">
    <tr><td style="padding:6px;color:#555">Keyword</td><td style="padding:6px"><strong>{keyword}</strong></td></tr>
    <tr><td style="padding:6px;color:#555">{scope_label}</td><td style="padding:6px"><strong>{scope_value}</strong></td></tr>
    <tr><td style="padding:6px;color:#555">Jobs found</td><td style="padding:6px"><strong>{job_count}</strong></td></tr>
    <tr><td style="padding:6px;color:#555">File</td><td style="padding:6px">{fname}</td></tr>
  </table>
  <br>
  {button_html}
</div>
"""

    payload = json.dumps(
        {
            "sender":      {"name": "LinkedIn Scraper", "email": from_email},
            "to":          [{"email": notify_email}],
            "subject":     f"LinkedIn Scrape Done: {job_count} '{keyword}' jobs in {scope_value}",
            "textContent": text_body,
            "htmlContent": html_body,
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
