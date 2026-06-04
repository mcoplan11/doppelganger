"""Send transactional emails via Resend.

If RESEND_API_KEY is empty (local dev), just prints the link to stdout.
"""
import resend

from app_config import settings

ADMIN_EMAIL = "hello@doppelgangerlabs.com"


def _send(to: str, subject: str, html: str) -> None:
    if not settings.resend_api_key:
        print(f"\n[DEV] Email to {to}\nSubject: {subject}\n{html}\n")
        return
    resend.api_key = settings.resend_api_key
    resend.Emails.send({"from": settings.from_email, "to": to, "subject": subject, "html": html})


def send_magic_link(to_email: str, magic_url: str) -> None:
    _send(
        to_email,
        "Your login link for Doppelganger",
        f"""
        <p>Click the link below to log in. It expires in 15 minutes.</p>
        <p><a href="{magic_url}" style="font-size:18px">Log in →</a></p>
        <p style="color:#888;font-size:12px">If you didn't request this, ignore this email.</p>
        """,
    )


def send_run_notification(
    *,
    run_id: int,
    user_email: str,
    survey_id: str,
    ai_survey_id: str | None,
    is_smoke: bool,
    status: str,
    credits_used: int,
    n_participants: int,
    duration_seconds: int,
    branch_counts: dict,
    error: str | None,
) -> None:
    """Email the admin when a simulation run finishes (any outcome)."""
    try:
        run_type = "Trial run" if is_smoke else "Simulation"
        mins, secs = divmod(duration_seconds, 60)
        duration = f"{mins}m {secs}s" if mins else f"{secs}s"
        icon = "✅" if status == "done" else "⚠️"
        subject = f"{icon} {run_type} #{run_id} {status} — {survey_id}"

        conditions_html = ""
        if branch_counts:
            rows = "".join(
                f"<tr><td style='padding:2px 12px 2px 0'>{k}</td>"
                f"<td style='padding:2px 0'><b>{v}</b></td></tr>"
                for k, v in branch_counts.items()
            )
            conditions_html = f"<p><b>Conditions:</b></p><table>{rows}</table>"

        error_html = (
            f"<p style='color:#c00'><b>Error:</b> {error}</p>" if error else ""
        )

        html = f"""
        <h2 style='margin-bottom:4px'>{icon} {run_type} #{run_id}: <code>{status}</code></h2>
        <table style='margin:16px 0;border-collapse:collapse'>
          <tr><td style='padding:2px 12px 2px 0;color:#666'>User</td><td><b>{user_email}</b></td></tr>
          <tr><td style='padding:2px 12px 2px 0;color:#666'>Survey</td><td><code>{survey_id}</code></td></tr>
          {"<tr><td style='padding:2px 12px 2px 0;color:#666'>AI copy</td><td><code>" + ai_survey_id + "</code></td></tr>" if ai_survey_id else ""}
          <tr><td style='padding:2px 12px 2px 0;color:#666'>Participants</td><td><b>{credits_used} / {n_participants}</b></td></tr>
          <tr><td style='padding:2px 12px 2px 0;color:#666'>Duration</td><td>{duration}</td></tr>
          <tr><td style='padding:2px 12px 2px 0;color:#666'>Type</td><td>{run_type}</td></tr>
        </table>
        {conditions_html}
        {error_html}
        """

        _send(ADMIN_EMAIL, subject, html)
    except Exception as e:
        # Never let a notification failure affect the run outcome
        print(f"[run {run_id}] admin notification failed: {e}", flush=True)
