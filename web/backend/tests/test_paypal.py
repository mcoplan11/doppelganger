"""Tests for the PayPal credit-purchase endpoints in main.py.

PayPal's API is mocked at the payments-module boundary (create/capture), so
these assert the endpoint logic only: the pending Purchase written at order
creation, credit fulfilment on capture, idempotent re-capture, and the
not-completed failure path. No network calls.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# The repo root also has a main.py (the CLI simulator) and simulator_runner puts
# the root on sys.path — make sure `import main` resolves to the backend app.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main as m  # noqa: E402
from auth import get_current_user
from database import Base, CreditBalance, Purchase, User, get_db


@pytest.fixture
def ctx(monkeypatch):
    """In-memory DB + auth/paypal stubs. Yields (client, db, user)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    user = User(email="buyer@example.com")
    db.add(user)
    db.flush()
    db.add(CreditBalance(user_id=user.id, balance=10))
    db.commit()

    def override_db():
        yield db

    m.app.dependency_overrides[get_db] = override_db
    m.app.dependency_overrides[get_current_user] = lambda: user

    # Stub the PayPal API boundary (names imported into main).
    monkeypatch.setattr(m, "create_paypal_order", lambda pack_id, user_email: "ORDER123")
    monkeypatch.setattr(m, "capture_paypal_order", lambda order_id: {"status": "COMPLETED"})

    # Plain TestClient (no context manager) so startup events — create_tables
    # on the real engine, the reaper loop — never run.
    client = TestClient(m.app)
    try:
        yield client, db, user
    finally:
        m.app.dependency_overrides.clear()
        db.close()


def _pack():
    from payments import CREDIT_PACKS
    return CREDIT_PACKS[0]


def test_create_order_writes_pending_purchase(ctx):
    client, db, user = ctx
    resp = client.post("/credits/paypal/orders", json={"pack_id": _pack()["id"]})
    assert resp.status_code == 200
    assert resp.json() == {"order_id": "ORDER123"}

    purchase = db.query(Purchase).filter(Purchase.paypal_order_id == "ORDER123").one()
    assert purchase.user_id == user.id
    assert purchase.provider == "paypal"
    assert purchase.status == "pending"
    assert purchase.credits == _pack()["credits"]
    assert purchase.amount_cents == _pack()["price_cents"]


def test_capture_fulfils_credits_once(ctx):
    client, db, user = ctx
    client.post("/credits/paypal/orders", json={"pack_id": _pack()["id"]})

    resp = client.post("/credits/paypal/orders/ORDER123/capture")
    assert resp.status_code == 200
    expected = 10 + _pack()["credits"]
    assert resp.json() == {"credits_added": _pack()["credits"], "balance": expected}

    # Re-capture (double click / retry) must not double-credit.
    resp2 = client.post("/credits/paypal/orders/ORDER123/capture")
    assert resp2.status_code == 200
    assert resp2.json() == {"credits_added": 0, "balance": expected}

    bal = db.query(CreditBalance).filter(CreditBalance.user_id == user.id).one()
    assert bal.balance == expected
    purchase = db.query(Purchase).filter(Purchase.paypal_order_id == "ORDER123").one()
    assert purchase.status == "paid"


def test_capture_unknown_order_404(ctx):
    client, _, _ = ctx
    resp = client.post("/credits/paypal/orders/NOPE/capture")
    assert resp.status_code == 404


def test_capture_not_completed_adds_nothing(ctx, monkeypatch):
    client, db, user = ctx
    client.post("/credits/paypal/orders", json={"pack_id": _pack()["id"]})
    monkeypatch.setattr(m, "capture_paypal_order", lambda order_id: {"status": "PAYER_ACTION_REQUIRED"})

    resp = client.post("/credits/paypal/orders/ORDER123/capture")
    assert resp.status_code == 402

    bal = db.query(CreditBalance).filter(CreditBalance.user_id == user.id).one()
    assert bal.balance == 10
    purchase = db.query(Purchase).filter(Purchase.paypal_order_id == "ORDER123").one()
    assert purchase.status == "pending"


def test_create_order_unknown_pack_400(ctx):
    client, _, _ = ctx
    resp = client.post("/credits/paypal/orders", json={"pack_id": "mega"})
    assert resp.status_code == 400
