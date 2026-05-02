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


settings = Settings()
