"""Magic-link authentication.

Flow:
  1. POST /auth/request  { email }  → generates a signed token, emails it
  2. GET  /auth/verify?token=xxx   → validates token, sets session cookie, redirects to dashboard
  3. POST /auth/logout             → clears session cookie

Session = opaque token stored in a signed cookie. On each request we look up
the token in the sessions table to get the user_id.
"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, Depends, HTTPException, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app_config import settings
from database import User, get_db


_signer = URLSafeTimedSerializer(settings.secret_key, salt="magic-link")

COOKIE_NAME = "session"


# ── Magic link tokens ────────────────────────────────────────────────────────

def make_magic_token(email: str) -> str:
    """Return a signed token encoding the email. Valid for magic_link_expiry seconds."""
    return _signer.dumps(email)


def verify_magic_token(token: str) -> str:
    """Return email from token or raise HTTPException."""
    try:
        email = _signer.loads(token, max_age=settings.magic_link_expiry)
        return email
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Magic link has expired. Request a new one.")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid magic link.")


# ── Session cookies ──────────────────────────────────────────────────────────

def create_session_cookie(response: Response, user_id: int) -> str:
    """Generate an opaque session token, set it as an httpOnly cookie, return the token."""
    token = secrets.token_urlsafe(32)
    signed = _signer.dumps({"uid": user_id, "tok": token})
    # Cross-site cookies (Railway backend → Vercel frontend) require SameSite=None + Secure.
    # Local dev over http falls back to Lax so the cookie still works without HTTPS.
    is_https = settings.frontend_url.startswith("https://")
    response.set_cookie(
        COOKIE_NAME,
        signed,
        max_age=settings.session_expiry,
        httponly=True,
        samesite="none" if is_https else "lax",
        secure=is_https,
    )
    return token


def _decode_session_cookie(cookie: str) -> int:
    """Return user_id from signed session cookie or raise HTTPException."""
    try:
        data = _signer.loads(cookie, max_age=settings.session_expiry)
        return int(data["uid"])
    except (SignatureExpired, BadSignature, KeyError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please log in again.",
        )


def get_current_user(
    session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in.")
    user_id = _decode_session_cookie(session)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user
