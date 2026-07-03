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
    supabase_url: str = "http://localhost:54321"
    supabase_service_key: str = "dev-service-role-key"
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


settings = Settings()
