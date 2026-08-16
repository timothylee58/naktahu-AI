import os
import secrets

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Used only when JWT_SECRET isn't set in the environment. A previous fixed
# string default here ("dev-jwt-secret-change-me-min-32-chars!!") was a
# critical vulnerability: if a deployment ever forgot to set JWT_SECRET, that
# exact string — public in this repo's history — could forge a JWT with
# app_metadata.role=primary_admin (services/auth.py effective_plan() promotes
# that straight to the business tier) and get free unlimited access.
#
# A per-process random secret closes that hole for a single-process run
# (tests, local dev), but Railway's Dockerfile sets ENV=production and runs
# multiple workers/containers — each would mint its own random secret and
# reject tokens signed by the others, an intermittent-401 outage that's
# worse than the vulnerability it replaces. So in production this fails
# loudly at startup instead: an operator missing JWT_SECRET should see a
# crash-on-boot, not silent multi-worker auth breakage or a forgeable token.
def _fallback_jwt_secret() -> str:
    """Computed once at import time (not per Settings() call) so multiple
    instantiations within the same process — this module's own `settings`
    singleton plus any test that constructs Settings() directly — agree on
    the same fallback value instead of each minting a different one."""
    is_production = os.environ.get("ENV", "development") == "production"
    if is_production and not os.environ.get("JWT_SECRET"):
        raise RuntimeError(
            "JWT_SECRET is not set. Refusing to start in production (ENV=production) "
            "with a random per-process secret, which would cause other workers/"
            "containers to reject each other's tokens. Set JWT_SECRET explicitly."
        )
    return secrets.token_urlsafe(32)


_FALLBACK_JWT_SECRET = _fallback_jwt_secret()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_secret: str = Field(
        default_factory=lambda: _FALLBACK_JWT_SECRET,
        validation_alias=AliasChoices("JWT_SECRET", "jwt_secret"),
    )
    supabase_jwt_aud: str = "authenticated"
    redis_url: str = "redis://localhost:6379/0"
    supabase_url: str = Field(
        default="http://localhost:54321",
        validation_alias=AliasChoices("SUPABASE_URL", "supabase_url"),
    )
    supabase_service_key: str = Field(
        default="dev-service-role-key",
        validation_alias=AliasChoices(
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_SERVICE_KEY",
            "supabase_service_key",
        ),
    )
    # Supabase direct Postgres — LangGraph PostgresSaver (use port 5432, not pooler).
    database_url: str = Field(
        default="",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )
    supabase_storage_bucket: str = Field(
        default="generated-documents",
        validation_alias=AliasChoices("SUPABASE_STORAGE_BUCKET", "supabase_storage_bucket"),
    )
    # Static bearer token required to scrape GET /metrics (Prometheus can't do
    # the JWT login flow get_current_user uses). Empty = endpoint always 401s
    # — fail closed on an unconfigured environment, never fail open.
    metrics_auth_token: str = Field(
        default="",
        validation_alias=AliasChoices("METRICS_AUTH_TOKEN", "metrics_auth_token"),
    )
    resend_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("RESEND_API_KEY", "resend_api_key"),
    )
    resend_from_email: str = Field(
        default="NakTahu <noreply@naktahu.ai>",
        validation_alias=AliasChoices("RESEND_FROM_EMAIL", "resend_from_email"),
    )
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
    )
    # Defaults OFF: production observed the ILMU-backed soft classifier
    # wrongly flag three unrelated, thoroughly benign civic queries as
    # harmful (lost ID document, contacting an MP, registering a company)
    # despite two rounds of system-prompt tuning (see guard_node.py's
    # _GUARD_LLM_SYSTEM_PROMPT history). The hard keyword layer
    # (_is_blocked_intent) stays fully active regardless of this setting —
    # only the flaky second-pass LLM check is gated by it. Re-enable via
    # GUARD_LLM_CHECK_ENABLED=true once the classifier's real-world
    # false-positive rate has been investigated and brought down.
    guard_llm_check_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("GUARD_LLM_CHECK_ENABLED", "guard_llm_check_enabled"),
    )

    frontend_url: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("FRONTEND_URL", "frontend_url"),
    )
    # This API's own public URL — needed to hand HitPay a webhook callback
    # address per-request (Stripe's webhook URL is configured once in its
    # dashboard instead, so it has no equivalent setting here).
    public_api_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("PUBLIC_API_URL", "public_api_url"),
    )
    stripe_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_SECRET_KEY", "stripe_secret_key"),
    )
    stripe_webhook_secret: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_WEBHOOK_SECRET", "stripe_webhook_secret"),
    )
    # Stripe Price IDs — one per checkout item. Configured in the Stripe
    # dashboard; referenced by name only, never hardcoded here.
    stripe_price_pro_individu: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_PRICE_PRO_INDIVIDU", "stripe_price_pro_individu"),
    )
    stripe_price_pro_perniagaan: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_PRICE_PRO_PERNIAGAAN", "stripe_price_pro_perniagaan"),
    )
    stripe_price_student: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_PRICE_STUDENT", "stripe_price_student"),
    )
    # Annual variants — same plan claim as their monthly counterpart, just a
    # different Stripe Price (10x monthly for pro/business ~= 2 months free;
    # student is a steeper 75%-off annual price). Separate Stripe Price IDs,
    # not a discount applied at checkout time, since Stripe subscriptions are
    # priced per-Price.
    stripe_price_pro_individu_annual: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_PRICE_PRO_INDIVIDU_ANNUAL", "stripe_price_pro_individu_annual"),
    )
    stripe_price_pro_perniagaan_annual: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_PRICE_PRO_PERNIAGAAN_ANNUAL", "stripe_price_pro_perniagaan_annual"),
    )
    stripe_price_student_annual: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_PRICE_STUDENT_ANNUAL", "stripe_price_student_annual"),
    )
    stripe_price_credits_5: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_PRICE_CREDITS_5", "stripe_price_credits_5"),
    )
    stripe_price_credits_20: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_PRICE_CREDITS_20", "stripe_price_credits_20"),
    )
    stripe_price_credits_50: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_PRICE_CREDITS_50", "stripe_price_credits_50"),
    )

    # HitPay — FPX/DuitNow QR checkout for agent-credit top-ups only (see
    # services/billing.py). Not used for subscription plans; HitPay's
    # recurring billing surface hasn't been evaluated yet.
    hitpay_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("HITPAY_API_KEY", "hitpay_api_key"),
    )
    # The webhook HMAC secret — a separate value from the API key, found
    # under Payment Gateway > Payment Requests > Webhook in the dashboard.
    hitpay_salt: str = Field(
        default="",
        validation_alias=AliasChoices("HITPAY_SALT", "hitpay_salt"),
    )
    hitpay_base_url: str = Field(
        default="https://api.sandbox.hit-pay.com/v1",
        validation_alias=AliasChoices("HITPAY_BASE_URL", "hitpay_base_url"),
    )

    # ── Deadline Monitor calendar sync (migration 039) ──────────────────────
    # Write-only OAuth: NakTahu creates/updates/deletes calendar EVENTS for a
    # user's subscribed deadlines, never reads their existing calendar. All
    # four *_client_id/_client_secret values come from apps YOU must register
    # yourself (Google Cloud Console + Microsoft Entra — this sandbox has no
    # account/browser access to do it) — see services/calendar_sync.py's
    # module docstring for the exact registration steps and redirect URIs.
    # Empty default (not a placeholder-looking value) so a missing credential
    # fails loudly/obviously rather than silently trying garbage against the
    # real OAuth endpoint.
    google_calendar_client_id: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_CALENDAR_CLIENT_ID", "google_calendar_client_id"),
    )
    google_calendar_client_secret: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_CALENDAR_CLIENT_SECRET", "google_calendar_client_secret"),
    )
    microsoft_calendar_client_id: str = Field(
        default="",
        validation_alias=AliasChoices("MICROSOFT_CALENDAR_CLIENT_ID", "microsoft_calendar_client_id"),
    )
    microsoft_calendar_client_secret: str = Field(
        default="",
        validation_alias=AliasChoices("MICROSOFT_CALENDAR_CLIENT_SECRET", "microsoft_calendar_client_secret"),
    )
    # Fernet key (44-char urlsafe-base64, from `Fernet.generate_key()`) used
    # to encrypt refresh tokens at rest in calendar_connections — the only
    # long-lived calendar secret this app stores. Never derived from
    # jwt_secret or any other existing secret: a leak of one must not also
    # compromise the other.
    calendar_token_encryption_key: str = Field(
        default="",
        validation_alias=AliasChoices("CALENDAR_TOKEN_ENCRYPTION_KEY", "calendar_token_encryption_key"),
    )


settings = Settings()
