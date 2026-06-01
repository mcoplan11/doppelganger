"""Send transactional emails via Resend.

If RESEND_API_KEY is empty (local dev), just prints the link to stdout.
"""
import resend

from config import settings


def send_magic_link(to_email: str, magic_url: str) -> None:
    if not settings.resend_api_key:
        # Local dev — print instead of sending
        print(f"\n[DEV] Magic link for {to_email}:\n  {magic_url}\n")
        return

    resend.api_key = settings.resend_api_key
    resend.Emails.send({
        "from": settings.from_email,
        "to": to_email,
        "subject": "Your login link for Doppelganger",
        "html": f"""
        <p>Click the link below to log in. It expires in 15 minutes.</p>
        <p><a href="{magic_url}" style="font-size:18px">Log in →</a></p>
        <p style="color:#888;font-size:12px">If you didn't request this, ignore this email.</p>
        """,
    })
