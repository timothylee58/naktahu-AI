from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    jwt_secret: str = Field(
        default="dev-jwt-secret-change-me-min-32-chars!!",
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
    guard_llm_check_enabled: bool = Field(
        default=True,
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


settings = Settings()
