"""FastAPI application — Doppelganger web service."""
# truststore must wrap the ssl module BEFORE urllib3/requests are first imported
# (payments.py and stripe both pull in requests below). Injecting after urllib3
# has captured the original SSLContext causes infinite recursion in ssl.py's
# verify_mode setter on every HTTPS call. simulator_runner injects again later —
# that's a harmless no-op once this has run.
import truststore

truststore.inject_into_ssl()

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import stripe
from fastapi import BackgroundTasks, Body, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import create_session_cookie, get_current_user, make_magic_token, verify_magic_token
from app_config import settings
from crypto import decrypt, encrypt
from database import CreditBalance, Purchase, Run, SessionLocal, User, create_tables, get_db
from email_client import send_magic_link, send_run_notification
from payments import (
    CREDIT_PACKS,
    capture_paypal_order,
    construct_webhook_event,
    create_checkout_session,
    create_paypal_order,
    get_pack,
)
from rate_limit import SlidingWindowLimiter
from simulator_runner import run_simulation


def _bootstrap_gcp_credentials() -> None:
    """Materialize a GCP service-account key from an env var into a file.

    Railway (and most PaaS) only provide env vars, but Google's Application
    Default Credentials needs a file path in GOOGLE_APPLICATION_CREDENTIALS. If
    GCP_SA_KEY_B64 is set, decode it to disk and point ADC at it. No-ops locally
    (where ADC is configured via `gcloud auth application-default login`), so it
    is safe to always call. Must run before any Vertex client is constructed.
    """
    import base64

    b64 = os.environ.get("GCP_SA_KEY_B64")
    if not b64:
        return
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/gcp-sa.json")
    try:
        data = base64.b64decode(b64)
        with open(cred_path, "wb") as f:
            f.write(data)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
        print(f"[startup] wrote GCP credentials to {cred_path} ({len(data)} bytes)",
              flush=True)
    except Exception as exc:  # never crash boot over this — /health will show it
        print(f"[startup] failed to materialize GCP credentials: {exc}", flush=True)


_bootstrap_gcp_credentials()

app = FastAPI(title="Doppelganger API", version="1.0.0")

_allowed_origins = list({
    settings.frontend_url,
    "http://localhost:3000",
    "https://doppelganger-two.vercel.app",
    "https://doppelgangerlabs.com",
    "https://www.doppelgangerlabs.com",
})

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_BOOT_TIME = datetime.now(timezone.utc).isoformat()

# Best-effort abuse throttle for the unauthenticated magic-link endpoint.
# Tuned to favor real users: the per-recipient limit is what stops email
# bombing (a human needs 1-2 links); the per-IP cap is a deliberately loose
# backstop because Railway routes every user through one proxy IP and our
# users often share university NAT, so a tight per-IP limit would throttle
# everyone at once. Easily tuned — raise if any real user ever trips it.
_auth_limiter = SlidingWindowLimiter()
_MAGIC_LINK_RULES_FOR = lambda email, ip: [
    (f"magiclink:email:{email}", 5, 900),   # 5 per recipient per 15 min
    (f"magiclink:ip:{ip}", 100, 900),        # 100 per source IP per 15 min
]


def _client_ip(request: Request) -> str:
    """Real client IP behind Railway's proxy (X-Forwarded-For first hop)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.get("/health")
def health():
    """Liveness + deployed-version probe.

    `commit` is Railway's injected RAILWAY_GIT_COMMIT_SHA (the deployed SHA);
    `booted_at` resets on every restart/redeploy. Used to confirm a deploy is
    live before kicking off a run.
    """
    # Safe config diagnostics — booleans only, never the secret values. Lets us
    # confirm whether the backend PROCESS actually sees each key without Railway
    # dashboard access.
    return {
        "status": "ok",
        "commit": os.environ.get("RAILWAY_GIT_COMMIT_SHA", "unknown"),
        "booted_at": _BOOT_TIME,
        "config": {
            "gemini_backend": "vertex" if settings.gemini_use_vertex else "ai_studio",
            "gemini_project": settings.gemini_project if settings.gemini_use_vertex else "",
            "gemini_location": settings.gemini_location,
            "gcp_credentials_present": bool(
                os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            ),
            "gemini_key_set": bool(settings.gemini_api_key),
            "openrouter_key_set": bool(settings.openrouter_api_key),
            "openrouter_env_present": "OPENROUTER_API_KEY" in os.environ,
            "openrouter_key_len": len(settings.openrouter_api_key or ""),
        },
    }


@app.on_event("startup")
async def startup():
    create_tables()
    asyncio.create_task(_reaper_loop())


async def _reaper_loop() -> None:
    """Proactively reap and notify stuck runs every 5 minutes.

    The on-read reaper in _reap_stuck_runs only fires when a user hits /runs.
    Runs orphaned by a Railway restart would never be caught if no one checks.
    This loop ensures we always notify even when users aren't watching.
    """
    while True:
        await asyncio.sleep(5 * 60)
        try:
            db = SessionLocal()
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_RUN_MINUTES)
                stuck = (
                    db.query(Run)
                    .filter(Run.status.in_(["converting", "running"]))
                    .filter(
                        func.coalesce(Run.last_heartbeat_at, Run.created_at) < cutoff
                    )
                    .all()
                )
                if stuck:
                    _reap_stuck_runs(db, stuck)
            finally:
                db.close()
        except Exception as e:
            print(f"[reaper-loop] error: {e}", file=sys.stderr, flush=True)


# ── Auth ─────────────────────────────────────────────────────────────────────

class MagicLinkRequest(BaseModel):
    email: EmailStr


@app.post("/auth/request")
def request_magic_link(body: MagicLinkRequest, request: Request, db: Session = Depends(get_db)):
    """Send a magic link email. Creates user if first time."""
    # Abuse throttle. On limit hit we return the SAME success response and just
    # skip the send: a real user who somehow trips it already has valid links in
    # their inbox, so login still works, while a bot gets a silent no-op and no
    # user row is created. Fails OPEN — any limiter error allows the request.
    try:
        ip = _client_ip(request)
        allowed = _auth_limiter.allow(_MAGIC_LINK_RULES_FOR(body.email.lower(), ip))
    except Exception as exc:  # never let the throttle break login
        print(f"[rate-limit] limiter error, allowing request: {exc}", flush=True)
        allowed = True
    if not allowed:
        print(f"[rate-limit] suppressed magic link for {body.email} from {ip}", flush=True)
        return {"detail": "Magic link sent. Check your email."}

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
    try:
        send_magic_link(body.email, magic_url)
    except Exception as exc:
        # Don't let an email-provider failure surface as an uncaught 500 (which
        # loses CORS headers and shows the browser a useless "failed to fetch").
        # Return a clean, readable error instead.
        print(f"Magic link send failed for {body.email}: {exc}", flush=True)
        raise HTTPException(
            status_code=502,
            detail="We couldn't send the login email right now. Please try again "
                   "in a moment, or contact support if it keeps happening.",
        )
    return {"detail": "Magic link sent. Check your email."}


@app.get("/auth/verify")
def verify_magic_link(token: str, db: Session = Depends(get_db)):
    """Validate token, set session cookie, redirect to dashboard."""
    email = verify_magic_token(token)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    # Set cookie on the RedirectResponse directly — FastAPI discards
    # cookies set on the injected `response` parameter when the handler
    # returns a different Response object.
    redirect = RedirectResponse(url=f"{settings.frontend_url}/dashboard", status_code=302)
    create_session_cookie(redirect, user.id)
    return redirect


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
        "qualtrics_datacenter": user.qualtrics_datacenter,
        "qualtrics_token": decrypt(user.qualtrics_token_enc) if user.qualtrics_token_enc else None,
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


# PayPal credit purchases (Orders v2, sandbox by default — see app_config).
# Two-step server-side flow driven by the PayPal Buttons on the dashboard:
#   1. POST /credits/paypal/orders            → create order (price from pack, never client)
#   2. buyer approves in the PayPal popup
#   3. POST /credits/paypal/orders/{id}/capture → capture + fulfil credits
# A pending Purchase row is written at order creation so capture can verify the
# order belongs to the calling user and fulfil idempotently.

@app.post("/credits/paypal/orders")
def create_paypal_credit_order(
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pack = get_pack(body.pack_id)
    order_id = create_paypal_order(pack_id=body.pack_id, user_email=user.email)
    db.add(Purchase(
        user_id=user.id,
        provider="paypal",
        paypal_order_id=order_id,
        credits=pack["credits"],
        amount_cents=pack["price_cents"],
        status="pending",
    ))
    db.commit()
    return {"order_id": order_id}


@app.post("/credits/paypal/orders/{order_id}/capture")
def capture_paypal_credit_order(
    order_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    purchase = (
        db.query(Purchase)
        .filter(Purchase.paypal_order_id == order_id, Purchase.user_id == user.id)
        .first()
    )
    if not purchase:
        raise HTTPException(status_code=404, detail="Order not found.")

    bal = db.query(CreditBalance).filter(CreditBalance.user_id == user.id).first()
    if not bal:
        bal = CreditBalance(user_id=user.id, balance=0)
        db.add(bal)

    # Idempotency: a re-capture (double click, retry) must not double-credit.
    if purchase.status == "paid":
        return {"credits_added": 0, "balance": bal.balance}

    order = capture_paypal_order(order_id)
    if order.get("status") != "COMPLETED":
        raise HTTPException(status_code=402, detail="PayPal payment was not completed.")

    purchase.status = "paid"
    bal.balance += purchase.credits
    bal.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"credits_added": purchase.credits, "balance": bal.balance}


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
    smoke_test: bool = False  # if True, run 3 participants, don't deduct credits
    platform: str = "prolific"  # prolific | mturk


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
    n = 3 if body.smoke_test else body.n_participants

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

    token_enc = encrypt(body.qualtrics_token)

    # Persist credentials to the user profile so future runs are pre-filled.
    user.qualtrics_token_enc = token_enc
    user.qualtrics_datacenter = body.qualtrics_datacenter

    run = Run(
        user_id=user.id,
        original_survey_id=survey_id,
        qualtrics_datacenter=body.qualtrics_datacenter,
        qualtrics_token_enc=token_enc,
        n_participants=n,
        is_smoke_test=body.smoke_test,
        platform=body.platform,
        status="converting",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(run_simulation, run.id)
    return _run_to_dict(run)


# A run that's been active far longer than any plausible runtime was almost
# certainly orphaned by a backend restart (simulations run as in-process
# background tasks, so a redeploy kills them mid-flight and nothing ever updates
# the row). Trial runs finish in ~2 min and normal batch runs in minutes, so this
# threshold is deliberately generous to avoid reaping a legitimately long run.
STUCK_RUN_MINUTES = 120


def _reap_stuck_runs(db: Session, runs: list[Run]) -> None:
    """Mark long-orphaned active runs as failed. Self-heals on read so a run
    interrupted by a deploy or a Gemini stall doesn't spin forever."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_RUN_MINUTES)
    reaped: list[Run] = []
    for run in runs:
        if run.status not in ("converting", "running"):
            continue
        # Use last_heartbeat_at if available — a run actively calling _set_status
        # keeps bumping this, so we won't reap it while it's legitimately running.
        # Fall back to created_at for old rows that predate the column.
        last_active = run.last_heartbeat_at or run.created_at
        if last_active is None:
            continue
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=timezone.utc)
        if last_active < cutoff:
            completed_at = datetime.now(timezone.utc)
            run.status = "failed"
            run.error = (
                "This run didn't complete in time — it may have been interrupted "
                "by a server update or a Gemini API issue. No credits were charged "
                "— please start it again."
            )
            run.completed_at = completed_at
            reaped.append(run)
    if reaped:
        db.commit()
        # Notify admin for each reaped run (same visibility as normal failures)
        for run in reaped:
            try:
                user_email = run.user.email if run.user else "unknown"
                created = run.created_at
                if created and created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                # After db.commit() above, SQLAlchemy expires these attributes, so
                # re-reading run.completed_at returns a naive datetime from Postgres.
                # Normalize before subtracting or it raises "can't subtract
                # offset-naive and offset-aware datetimes".
                completed = run.completed_at
                if completed and completed.tzinfo is None:
                    completed = completed.replace(tzinfo=timezone.utc)
                duration = int((completed - created).total_seconds()) if (created and completed) else 0
                send_run_notification(
                    run_id=run.id,
                    user_email=user_email,
                    survey_id=run.original_survey_id,
                    ai_survey_id=run.ai_survey_id,
                    is_smoke=run.is_smoke_test,
                    status="failed (reaped — stuck >{} min)".format(STUCK_RUN_MINUTES),
                    credits_used=run.credits_used or 0,
                    n_participants=run.n_participants,
                    duration_seconds=duration,
                    branch_counts={},
                    error=run.error,
                )
            except Exception as e:
                print(f"[reaper] notification failed for run {run.id}: {e}", flush=True)


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
    _reap_stuck_runs(db, runs)
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
    _reap_stuck_runs(db, [run])
    return _run_to_dict(run)


@app.post("/runs/{run_id}/cancel")
def cancel_run(
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.query(Run).filter(Run.id == run_id, Run.user_id == user.id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    if run.status in ("done", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Run is already {run.status}.")
    run.status = "cancelled"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    return _run_to_dict(run)


@app.get("/runs/{run_id}/results")
def get_run_results(
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.query(Run).filter(Run.id == run_id, Run.user_id == user.id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    # Prefer the DB-cached summary (survives Railway redeploys).
    if run.results_json:
        return json.loads(run.results_json)
    # Fallback: build from files (works on local dev or runs that completed
    # before results_json was introduced).
    if not run.result_path:
        return {"available": False, "questions": []}
    from results import build_results
    result = build_results(Path(run.result_path).parent)
    # Cache it now so future requests don't hit disk again.
    if result.get("available"):
        run.results_json = json.dumps(result)
        db.commit()
    return result


def _respondent_rows(run: Run) -> tuple[list[str], list[dict]]:
    """Flatten a run's per-session response files into tabular rows.

    Returns (columns, rows): columns is the union of keys in first-seen order so
    heterogeneous rows (e.g. branch-dependent questions) share one schema. Rows
    are tagged with the anonymized model label — never the real model name.
    """
    if not run.result_path:
        return [], []
    result_dir = Path(run.result_path).parent

    # Map model subdir slugs -> anonymized labels (Model A/B/C). Never expose the
    # real model behind a slug.
    slug_to_label: dict[str, str] = {}
    if run.ai_survey_ids:
        try:
            for slug, info in json.loads(run.ai_survey_ids).items():
                slug_to_label[slug] = info.get("label", slug)
        except Exception:
            pass

    # Ensemble runs write one subdir per model; legacy runs wrote files flat.
    completed = sorted(result_dir.glob("*/*_completed.json"))
    if not completed:
        completed = [(None, p) for p in sorted(result_dir.glob("*_completed.json"))]
    else:
        completed = [(p.parent.name, p) for p in completed]

    columns: list[str] = []
    rows: list[dict] = []
    for slug, jf in completed:
        try:
            with open(jf) as f:
                d = json.load(f)
        except Exception:
            continue
        row = {
            "model": slug_to_label.get(slug, slug) if slug else "",
            "persona": d.get("persona"),
            "branch": d.get("branch_description"),
            **d.get("embedded_data", {}),
            **{k: (v if not isinstance(v, (dict, list)) else json.dumps(v))
               for k, v in d.get("answers", {}).items()},
        }
        for key in row:
            if key not in columns:
                columns.append(key)
        rows.append(row)
    return columns, rows


@app.get("/runs/{run_id}/responses")
def get_run_responses(
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Respondent-level rows for the results data grid.

    Built from on-disk session files, so it can be unavailable for old runs
    after a redeploy — the frontend treats {available: false} as "hide grid".
    """
    run = db.query(Run).filter(Run.id == run_id, Run.user_id == user.id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    columns, rows = _respondent_rows(run)
    return {"available": bool(rows), "columns": columns, "rows": rows}


@app.get("/runs/{run_id}/download")
def download_run(
    run_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = db.query(Run).filter(Run.id == run_id, Run.user_id == user.id).first()
    if not run or not run.result_path:
        raise HTTPException(status_code=404, detail="Results not available yet.")

    columns, rows = _respondent_rows(run)
    if not rows:
        raise HTTPException(status_code=404, detail="Results not available yet.")

    # Build a CSV from individual response JSON files, tagged by model.
    import csv, io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, restval="")
    writer.writeheader()
    for row in rows:
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
    # Per-model AI copies, keyed by anonymized label (Model A/B/C). Real model
    # identities are never stored, so nothing to redact here.
    ai_copies: list[dict] = []
    if run.ai_survey_ids:
        try:
            for slug, info in json.loads(run.ai_survey_ids).items():
                ai_copies.append({
                    "slug": slug,
                    "label": info.get("label", slug),
                    "ai_survey_id": info.get("ai_survey_id"),
                })
        except Exception:
            pass
    return {
        "id": run.id,
        "original_survey_id": run.original_survey_id,
        "ai_survey_id": run.ai_survey_id,
        "ai_survey_copies": ai_copies,
        "n_participants": run.n_participants,
        "is_smoke_test": run.is_smoke_test,
        "platform": run.platform,
        "status": run.status,
        "credits_used": run.credits_used,
        "error": run.error,
        "branch_distribution": branch,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
    }
