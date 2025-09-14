# lib/notify.py
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import List, Optional

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))  # 465 (SSL) or 587 (STARTTLS, not used here)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "")

def _assert_cfg():
    missing = [k for k, v in {
        "SMTP_HOST": SMTP_HOST,
        "SMTP_PORT": SMTP_PORT,
        "SMTP_USER": SMTP_USER,
        "SMTP_PASS": SMTP_PASS,
        "SMTP_FROM": SMTP_FROM,
    }.items() if not v]
    if missing:
        raise RuntimeError(f"SMTP configuration missing: {', '.join(missing)}")

def send_email(to: List[str], subject: str, body: str, reply_to: Optional[str] = None):
    """
    Simple plaintext email sender via SMTP over SSL.
    """
    _assert_cfg()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = ", ".join(to)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
