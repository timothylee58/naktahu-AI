import time
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
import stripe
from fastapi.testclient import TestClient

import main as api_main
from core.config import settings
from middleware.rate_limit import anonymous_limiter, authenticated_limiter


def _auth_header(sub: str = "billing-user", plan: str = "free", email: str | None = None) -> dict[str, str]:
    payload = {
        "sub": sub,
        "aud": settings.supabase_jwt_aud,
        "exp": int(time.time()) + 3600,
        "app_metadata": {"plan": plan},
    }
    if email:
        payload["email"] = email
    tok = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
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
    table_mock.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    rpc_mock = MagicMock()
    rpc_mock.execute.return_value = MagicMock(data=None)

    sb = MagicMock()
    sb.table.return_value = table_mock
    sb.rpc.return_value = rpc_mock
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
        headers=_auth_header(sub="checkout-user", email="checkout-user@example.com"),
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"url": "https://checkout.stripe.com/test-session"}
    kwargs = create_mock.call_args.kwargs
    assert kwargs["mode"] == "subscription"
    assert kwargs["client_reference_id"] == "checkout-user"
    assert kwargs["customer_email"] == "checkout-user@example.com"
    assert kwargs["metadata"] == {"user_id": "checkout-user", "item": "pro_individu"}


def test_checkout_omits_email_when_jwt_has_none(client, monkeypatch):
    c, *_ = client
    fake_session = MagicMock()
    fake_session.url = "https://checkout.stripe.com/test-session"
    create_mock = MagicMock(return_value=fake_session)
    monkeypatch.setattr(stripe.checkout.Session, "create", create_mock)

    res = c.post(
        "/api/v1/billing/checkout",
        json={"item": "pro_individu"},
        headers=_auth_header(sub="no-email-user"),
    )
    assert res.status_code == 200, res.text
    assert create_mock.call_args.kwargs["customer_email"] is None


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


def test_webhook_500_when_secret_not_configured(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(settings, "stripe_webhook_secret", "")
    res = c.post(
        "/api/v1/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "anything"},
    )
    assert res.status_code == 500


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


def test_webhook_checkout_completed_adds_credits_via_rpc(client, monkeypatch):
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
    sb.rpc.assert_called_once()
    rpc_name, rpc_args = sb.rpc.call_args.args
    assert rpc_name == "add_agent_credits"
    assert rpc_args["p_user_id"] == "credits-user"
    assert rpc_args["p_amount"] == 5


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


def test_webhook_releases_claim_on_processing_failure(client, monkeypatch):
    """A transient failure after the event is claimed must not permanently
    blacklist it — Stripe's retry needs to be able to reprocess."""
    c, sb, table_mock = client
    event = {
        "id": "evt_fails_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_4",
                "metadata": {"user_id": "fail-user", "item": "pro_individu"},
            }
        },
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", MagicMock(return_value=event))
    sb.auth.admin.update_user_by_id.side_effect = RuntimeError("supabase admin API timeout")

    with pytest.raises(RuntimeError):
        c.post(
            "/api/v1/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "valid"},
        )

    table_mock.delete.return_value.eq.assert_called_once_with("stripe_event_id", "evt_fails_1")


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


def test_get_credits_503_when_supabase_unavailable(client, monkeypatch):
    c, *_ = client
    monkeypatch.setattr(api_main.app.state, "supabase", None)
    res = c.get("/api/v1/billing/credits", headers=_auth_header(sub="degraded-user"))
    assert res.status_code == 503
