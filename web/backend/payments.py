"""Stripe integration — Checkout sessions and webhook handling."""
import stripe
from fastapi import HTTPException

from app_config import settings

stripe.api_key = settings.stripe_secret_key

# Credit packs: (credits, price_cents, display_name, stripe_price_id_or_None)
# price_id is None → we use ad-hoc price_data (easier for dev; use Price IDs in prod)
CREDIT_PACKS = [
    {"id": "starter",  "credits": 50,  "price_cents": 999,  "label": "Starter",  "per": "$0.20"},
    {"id": "standard", "credits": 100, "price_cents": 1799, "label": "Standard", "per": "$0.18"},
    {"id": "pro",      "credits": 250, "price_cents": 3999, "label": "Pro",       "per": "$0.16"},
    {"id": "research", "credits": 500, "price_cents": 6999, "label": "Research",  "per": "$0.14"},
]

_PACK_BY_ID = {p["id"]: p for p in CREDIT_PACKS}


def create_checkout_session(pack_id: str, user_email: str, success_url: str, cancel_url: str) -> str:
    """Create a Stripe Checkout session and return its URL."""
    pack = _PACK_BY_ID.get(pack_id)
    if not pack:
        raise HTTPException(status_code=400, detail=f"Unknown pack id: {pack_id}")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        customer_email=user_email,
        line_items=[{
            "price_data": {
                "currency": "usd",
                "unit_amount": pack["price_cents"],
                "product_data": {
                    "name": f"{pack['label']} — {pack['credits']} credits",
                    "description": f"{pack['per']} per participant",
                },
            },
            "quantity": 1,
        }],
        metadata={
            "pack_id": pack_id,
            "credits": pack["credits"],
            "user_email": user_email,
        },
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
    )
    return session.url


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    try:
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature.")
