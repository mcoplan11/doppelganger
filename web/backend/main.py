"""FastAPI application — Doppelganger web service."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import stripe
from fastapi import BackgroundTasks, Body, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from auth import create_session_cookie, get_current_user, make_magic_token, verify_magic_token
from config import settings
from crypto import encrypt
from database import CreditBalance, Purchase, Run, User, create_tables, get_db
from email_client import send_magic_link
from payments import CREDIT_PACKS, construct_webhook_event, create_checkout_session
from simulator_runner import run_simulation

app = FastAPI(title="Doppelganger API", version="1.0.0")

_allowed_origins = list({
    settings.frontend_url,
    "http://localhost:3000",
    "https://doppelganger-two.vercel.app",
})

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    create_tables()


# ── Auth ─────────────────────────────────────────────────────────────────────

class MagicLinkRequest(BaseModel):
    email: EmailStr


@app.post("/auth/request")
def request_magic_link(body: MagicLinkRequest, db: Session = Depends(get_db)):
    """Send a magic link email. Creates user if first time."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        user = User(email=body.email)
        db.add(user)
        db.flush()
        bal = CreditBalance(user_id=user.id, balance=0)
        db.add(bal)
        db.commit()

    token = make_magic_token(body.email)
    magic_url = f"{settings.frontend_url}/auth/verify?token={token}"
    send_magic_link(body.email, magic_url)
    return {"detail": "Magic link sent. Check your email."}


@app.get("/auth/verify")
def verify_magic_link(token: str, response: Response, db: Session = Depends(get_db)):
    """Validate token, set session cookie, redirect to dashboard."""
    email = verify_magic_token(token)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    create_session_cookie(response, user.id)
    return RedirectResponse(url=f"{settings.frontend_url}/dashboard", status_code=302)


@app.post("/auth/logout")
def logout(response: Response):
    is_https = settings.frontend_url.startswith("https://")
    response.delete_cookie(
        "session",
        samesite="none" if is_https else "lax",
        secure=is_https,
    )
    return {"detail": "Logged out."}


# ── Me ───────────────────────────────────────────────────────────────────────

@app.get("/me")
def get_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bal = db.query(CreditBalance).filter(CreditBalance.user_id == user.id).first()
    return {
        "id": user.id,
        "email": user.email,
        "credits": bal.balance if bal else 0,
        "created_at": user.created_at,
    }


# ── Credits / Payments ───────────────────────────────────────────────────────

@app.get("/credits/packs")
def list_packs():
    return CREDIT_PACKS


class CheckoutRequest(BaseModel):
    pack_id: str


@app.post("/credits/checkout")
def create_checkout(
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
):
    url = create_checkout_session(
        pack_id=body.pack_id,
        user_email=user.email,
        success_url=f"{settings.frontend_url}/dashboard?purchase=success",
        cancel_url=f"{settings.frontend_url}/dashboard",
    )
    return {"checkout_url": url}


@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe events — fulfil credits on payment success."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    event = construct_webhook_event(payload, sig)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        stripe_session_id = session["id"]
        meta = session.get("metadata", {})
        email = meta.get("user_email") or session.get("customer_email")
        credits_to_add = int(meta.get("credits", 0))
        amount_cents = session.get("amount_total", 0)

        # Idempotency: skip if already processed
        existing = db.query(Purchase).filter(Purchase.stripe_session_id == stripe_session_id).first()
        if existing and existing.status == "paid":
            return {"received": True}

        user = db.query(User).filter(User.email == email).first()
        if not user:
            return {"received": True}  # shouldn't happen

        # Record purchase
        if not existing:
            purchase = Purchase(
                user_id=user.id,
                stripe_session_id=stripe_session_id,
                credits=credits_to_add,
                amount_cents=amount_cents,
                status="paid",
            )
            db.add(purchase)
        else:
            existing.status = "paid"

        # Add credits
        bal = db.query(CreditBalance).filter(CreditBalance.user_id == user.id).first()
        if not bal:
            bal = CreditBalance(user_id=user.id, balance=0)
            db.add(bal)
        bal.balance += credits_to_add
        bal.updated_at = datetime.now(timezone.utc)
        db.commit()

    return {"received": True}


# ── Runs ─────────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    survey_url: str           # full URL or just SV_... ID
    qualtrics_token: str
    qualtrics_datacenter: str = "yul1"
    n_participants: int
    smoke_test: bool = False  # if True, run 5 participants, don't deduct credits


def _extract_survey_id(survey_url: str) -> str:
    """Pull SV_... ID from a Qualtrics URL or return as-is if already an ID."""
    import re
    m = re.search(r"(SV_[A-Za-z0-9]+)", survey_url)
    if m:
        return m.group(1)
    raise HTTPException(status_code=400, detail="Could not extract survey ID from URL.")


@app.post("/runs")
def create_run(
    body: RunRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    survey_id = _extract_survey_id(body.survey_url)
    n = 5 if body.smoke_test else body.n_participants

    if n < 1 or n > 1000:
        raise HTTPException(status_code=400, detail="n_participants must be 1–1000.")

    # Check credits (smoke tests are free)
    if not body.smoke_test:
        bal = db.query(CreditBalance).filter(CreditBalance.user_id == user.id).first()
        if not bal or bal.balance < n:
            raise HTTPException(
                status_code=402,
                detail=f"Not enough credits. You have {bal.balance if bal else 0}, need {n}.",
            )

    run = Run(
        user_id=user.id,
        original_survey_id=survey_id,
        qualtrics_datacenter=body.qualtrics_datacenter,
        qualtrics_token_enc=encrypt(body.qualtrics_token),
        n_participants=n,
        is_smoke_test=body.smoke_test,
        status="converting",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(run_simulation, run.id)
    return _run_to_dict(run)


@app.get("/runs")
def list_runs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    runs = (
        db.query(Run)
        .filter(Run.user_id == user.id)
        .order_by(Run.created_at.desc())
        .limit(50)
        .all()
    )
    return [_run_to_dict(r) for r in runs]


@app.get("/runs/{run_id}")
def get_run(
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.query(Run).filter(Run.id == run_id, Run.user_id == user.id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _run_to_dict(run)


@app.get("/runs/{run_id}/download")
def download_run(
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.query(Run).filter(Run.id == run_id, Run.user_id == user.id).first()
    if not run or not run.result_path:
        raise HTTPException(status_code=404, detail="Results not available yet.")
    result_dir = Path(run.result_path).parent

    # Build a simple CSV from individual response JSON files
    import csv, io
    buf = io.StringIO()
    writer = None
    for jf in sorted(result_dir.glob("*_completed.json")):
        with open(jf) as f:
            d = json.load(f)
        row = {
            "persona": d.get("persona"),
            "branch": d.get("branch_description"),
            **d.get("embedded_data", {}),
            **{k: (v if not isinstance(v, (dict, list)) else json.dumps(v))
               for k, v in d.get("answers", {}).items()},
        }
        if writer is None:
            writer = csv.DictWriter(buf, fieldnames=list(row.keys()))
            writer.writeheader()
        writer.writerow(row)

    buf.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="run_{run_id}.csv"'},
    )


def _run_to_dict(run: Run) -> dict:
    branch = {}
    if run.branch_summary:
        try:
            branch = json.loads(run.branch_summary)
        except Exception:
            pass
    return {
        "id": run.id,
        "original_survey_id": run.original_survey_id,
        "ai_survey_id": run.ai_survey_id,
        "n_participants": run.n_participants,
        "is_smoke_test": run.is_smoke_test,
        "status": run.status,
        "credits_used": run.credits_used,
        "error": run.error,
        "branch_distribution": branch,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
    }
