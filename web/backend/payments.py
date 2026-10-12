"""Payments — Stripe Checkout and PayPal Orders v2."""
import requests
import stripe
from fastapi import HTTPException

from app_config import settings

stripe.api_key = settings.stripe_secret_key

# Credit packs: (credits, price_cents, display_name, stripe_price_id_or_None)
# price_id is None → we use ad-hoc price_data (easier for dev; use Price IDs in prod)
CREDIT_PACKS = [
    {"id": "starter",  "credits": 200,  "price_cents": 799,  "label": "Starter",  "per": "$0.04"},
    {"id": "standard", "credits": 600,  "price_cents": 1499, "label": "Standard", "per": "$0.025"},
    {"id": "pro",      "credits": 1200, "price_cents": 2499, "label": "Pro",       "per": "$0.02"},
]

_PACK_BY_ID = {p["id"]: p for p in CREDIT_PACKS}


def get_pack(pack_id: str) -> dict:
    pack = _PACK_BY_ID.get(pack_id)
    if not pack:
        raise HTTPException(status_code=400, detail=f"Unknown pack id: {pack_id}")
    return pack


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


# ── PayPal (Orders v2) ────────────────────────────────────────────────────────
# Server-side order create + capture. The frontend renders PayPal Buttons, but
# the amount and credits always come from CREDIT_PACKS here — the client only
# ever sends a pack_id, so a tampered browser can't change the price.

def _paypal_access_token() -> str:
    """Client-credentials OAuth token (sandbox or live per PAYPAL_BASE_URL)."""
    if not settings.paypal_client_id or not settings.paypal_client_secret:
        raise HTTPException(status_code=503, detail="PayPal is not configured.")
    try:
        resp = requests.post(
            f"{settings.paypal_base_url}/v1/oauth2/token",
            auth=(settings.paypal_client_id, settings.paypal_client_secret),
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"PayPal unreachable: {exc}")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="PayPal authentication failed.")
    return resp.json()["access_token"]


def create_paypal_order(pack_id: str, user_email: str) -> str:
    """Create a PayPal order for a credit pack and return its order ID."""
    pack = get_pack(pack_id)
    token = _paypal_access_token()
    try:
        resp = requests.post(
            f"{settings.paypal_base_url}/v2/checkout/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "intent": "CAPTURE",
                "purchase_units": [{
                    "reference_id": pack_id,
                    "custom_id": user_email,
                    "description": f"{pack['label']} — {pack['credits']} Doppelganger credits",
                    "amount": {
                        "currency_code": "USD",
                        "value": f"{pack['price_cents'] / 100:.2f}",
                    },
                }],
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"PayPal unreachable: {exc}")
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="PayPal order creation failed.")
    return resp.json()["id"]


def capture_paypal_order(order_id: str) -> dict:
    """Capture an approved PayPal order. Returns the order/capture payload.

    Tolerates double-capture: if PayPal reports ORDER_ALREADY_CAPTURED (e.g. a
    double-click or webhook race), fetch and return the order instead of failing
    so the caller can still verify its COMPLETED status idempotently.
    """
    token = _paypal_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        resp = requests.post(
            f"{settings.paypal_base_url}/v2/checkout/orders/{order_id}/capture",
            headers=headers,
            timeout=30,
        )
        if resp.status_code == 422 and "ORDER_ALREADY_CAPTURED" in resp.text:
            resp = requests.get(
                f"{settings.paypal_base_url}/v2/checkout/orders/{order_id}",
                headers=headers,
                timeout=30,
            )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"PayPal unreachable: {exc}")
    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="PayPal capture failed.")
    return resp.json()
