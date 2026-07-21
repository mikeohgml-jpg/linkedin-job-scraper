"""
Run this in the Railway console to verify Brevo email is working:

    python test_resend_railway.py
"""
import json
import os
import urllib.error
import urllib.request

api_key    = os.getenv("BREVO_API_KEY", "")
from_email = os.getenv("FROM_EMAIL") or os.getenv("SMTP_USER", "")
to_email   = os.getenv("NOTIFY_EMAIL", "")

print("── Brevo config check ───────────────────────")
print(f"  BREVO_API_KEY: {'✓ set' if api_key else '✗ MISSING'}")
print(f"  FROM_EMAIL   : {from_email or '✗ MISSING'}")
print(f"  NOTIFY_EMAIL : {to_email or '✗ MISSING'}")
print()

if not (api_key and from_email and to_email):
    print("One or more env vars are missing — fix them in Railway Variables then re-run.")
    raise SystemExit(1)

payload = json.dumps({
    "sender":      {"name": "LinkedIn Scraper", "email": from_email},
    "to":          [{"email": to_email}],
    "subject":     "Railway ✓ Brevo test",
    "textContent": "If you got this, Brevo is wired up correctly on Railway.",
}).encode("utf-8")

req = urllib.request.Request(
    "https://api.brevo.com/v3/smtp/email",
    data=payload,
    headers={"api-key": api_key, "Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(f"✓ Email sent! HTTP {resp.status}")
except urllib.error.HTTPError as exc:
    body = exc.read().decode("utf-8", errors="replace")
    print(f"✗ HTTP {exc.code}: {body}")
    raise SystemExit(1)
except Exception as exc:
    print(f"✗ {type(exc).__name__}: {exc}")
    raise SystemExit(1)
