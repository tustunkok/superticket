"""Pydantic-settings configuration for SuperTicket."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./superticket.db"
    debug: bool = False
    app_version: str = "0.1.0-alpha.1"


settings = Settings()
