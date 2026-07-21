"""
Run this in the Railway console to verify Resend SMTP is working:

    python test_resend_railway.py
"""
import os
import smtplib
from email.message import EmailMessage

api_key    = os.getenv("RESEND_API_KEY", "")
from_email = os.getenv("RESEND_FROM_EMAIL", "")
to_email   = os.getenv("NOTIFY_EMAIL", "")

print("── Resend SMTP config check ─────────────────")
print(f"  RESEND_API_KEY   : {'✓ ' + api_key[:10] + '...' if api_key else '✗ MISSING'}")
print(f"  RESEND_FROM_EMAIL: {from_email or '✗ MISSING'}")
print(f"  NOTIFY_EMAIL     : {to_email or '✗ MISSING'}")
print()

if not (api_key and from_email and to_email):
    print("One or more env vars are missing — fix them in Railway Variables then re-run.")
    raise SystemExit(1)

msg = EmailMessage()
msg["From"] = from_email
msg["To"] = to_email
msg["Subject"] = "Railway ✓ Resend SMTP test"
msg.set_content("If you got this, Resend SMTP is wired up correctly on Railway.")

try:
    with smtplib.SMTP_SSL("smtp.resend.com", 465, timeout=15) as server:
        server.login("resend", api_key)
        server.send_message(msg)
    print(f"✓ Email sent to {to_email}")
except smtplib.SMTPAuthenticationError as exc:
    print(f"✗ Auth error — check RESEND_API_KEY: {exc}")
    raise SystemExit(1)
except Exception as exc:
    print(f"✗ {type(exc).__name__}: {exc}")
    raise SystemExit(1)
