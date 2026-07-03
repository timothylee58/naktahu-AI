import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
import stripe
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter


def _auth_header(sub: str = "billing-user", plan: str = "free") -> dict[str, str]:
    tok = jwt.encode(
        {
            "sub": sub,
            "aud": settings.supabase_jwt_aud,
            "exp": int(time.time()) + 3600,
            "app_metadata": {"plan": plan},
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def client(monkeypatch):
    redis_client = AsyncMock()
    redis_client.ping = AsyncMock(return_value=True)
    redis_client.aclose = AsyncMock(return_value=None)

    def fake_from_url(*args, **kwargs):
        return redis_client

    monkeypatch.setattr(api_main.redis_ai, "from_url", fake_from_url)

    table_mock = MagicMock()
    table_mock.select.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    table_mock.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    table_mock.insert.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])
    table_mock.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "1"}])

    sb = MagicMock()
    sb.table.return_value = table_mock
    sb.auth.admin.update_user_by_id = MagicMock()

    monkeypatch.setattr(api_main, "create_client", lambda url, key: sb)

    monkeypatch.setattr(settings, "stripe_price_pro_individu", "price_pro_individu_test")
    monkeypatch.setattr(settings, "stripe_price_credits_5", "price_credits_5_test")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")

    anonymous_limiter.reset()
    authenticated_limiter.reset()

    with TestClient(api_main.app) as c:
        yield c, sb, table_mock


def test_checkout_requires_auth(client):
    c, *_ = client
    res = c.post("/api/v1/billing/checkout", json={"item": "pro_individu"})
    assert res.status_code == 401


def test_checkout_rejects_unknown_item(client):
    c, *_ = client
    res = c.post(
        "/api/v1/billing/checkout",
        json={"item": "not_a_real_item"},
        headers=_auth_header(),
    )
    assert res.status_code == 422


def test_checkout_creates_session_and_returns_url(client, monkeypatch):
    c, *_ = client
    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/test-session"
    create_mock = MagicMock(return_value=fake_session)
    monkeypatch.setattr(stripe.checkout.Session, "create", create_mock)

    res = c.post(
        "/api/v1/billing/checkout",
        json={"item": "pro_individu"},
        headers=_auth_header(sub="checkout-user"),
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"url": "https://checkout.stripe.com/test-session"}
    kwargs = create_mock.call_args.kwargs
    assert kwargs["mode"] == "subscription"
    assert kwargs["client_reference_id"] == "checkout-user"
    assert kwargs["metadata"] == {"user_id": "checkout-user", "item": "pro_individu"}


def test_checkout_503_when_price_not_configured(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(settings, "stripe_price_student", "")
    res = c.post(
        "/api/v1/billing/checkout",
        json={"item": "student"},
        headers=_auth_header(),
    )
    assert res.status_code == 503


def test_webhook_rejects_invalid_signature(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        MagicMock(side_effect=stripe.SignatureVerificationError("bad sig", "sig_header")),
    )
    res = c.post(
        "/api/v1/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "bad"},
    )
    assert res.status_code == 400


def test_webhook_checkout_completed_updates_plan(client, monkeypatch):
    c, sb, table_mock = client
    event = {
        "id": "evt_plan_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "metadata": {"user_id": "plan-user", "item": "pro_individu"},
            }
        },
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", MagicMock(return_value=event))

    res = c.post(
        "/api/v1/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "valid"},
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"status": "ok"}
    sb.auth.admin.update_user_by_id.assert_called_once_with(
        "plan-user", {"app_metadata": {"plan": "pro"}}
    )


def test_webhook_checkout_completed_adds_credits(client, monkeypatch):
    c, sb, table_mock = client
    event = {
        "id": "evt_credits_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_2",
                "metadata": {"user_id": "credits-user", "item": "credits_5"},
            }
        },
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", MagicMock(return_value=event))

    res = c.post(
        "/api/v1/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "valid"},
    )
    assert res.status_code == 200, res.text
    sb.table.assert_any_call("agent_credits")
    # insert is called twice: once for the stripe_events dedupe row, once
    # for the agent_credits topup — find the credits insert specifically.
    credit_inserts = [
        call.args[0] for call in table_mock.insert.call_args_list if "credits_remaining" in call.args[0]
    ]
    assert len(credit_inserts) == 1
    assert credit_inserts[0]["user_id"] == "credits-user"
    assert credit_inserts[0]["credits_remaining"] == 5


def test_webhook_duplicate_event_not_reprocessed(client, monkeypatch):
    c, sb, table_mock = client
    event = {
        "id": "evt_dup_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_3",
                "metadata": {"user_id": "dup-user", "item": "pro_individu"},
            }
        },
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", MagicMock(return_value=event))

    import postgrest.exceptions

    monkeypatch.setattr(
        table_mock.insert.return_value,
        "execute",
        MagicMock(side_effect=postgrest.exceptions.APIError({"code": "23505", "message": "duplicate"})),
    )

    res = c.post(
        "/api/v1/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "valid"},
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"status": "duplicate"}
    sb.auth.admin.update_user_by_id.assert_not_called()


def test_get_credits_requires_auth(client):
    c, *_ = client
    res = c.get("/api/v1/billing/credits")
    assert res.status_code == 401


def test_get_credits_returns_remaining(client):
    c, sb, table_mock = client
    table_mock.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"credits_remaining": 12}]
    )
    res = c.get("/api/v1/billing/credits", headers=_auth_header(sub="credit-check-user"))
    assert res.status_code == 200, res.text
    assert res.json() == {"credits_remaining": 12}


def test_get_credits_zero_when_no_row(client):
    c, *_ = client
    res = c.get("/api/v1/billing/credits", headers=_auth_header(sub="no-credits-user"))
    assert res.status_code == 200, res.text
    assert res.json() == {"credits_remaining": 0}
