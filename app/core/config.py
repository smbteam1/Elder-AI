"""Application configuration, loaded from environment / .env file."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Retell credentials — never hardcode, always read from env.
    retell_api_key: str = ""
    retell_agent_id: str = ""
    retell_from_number: str = ""

    # Database
    database_url: str = "sqlite:///./elder_ai.db"

    # Webhook signature verification. Defaults to True (production-safe).
    # Set VERIFY_WEBHOOK_SIGNATURE=false to simulate webhooks locally.
    verify_webhook_signature: bool = True


settings = Settings()
