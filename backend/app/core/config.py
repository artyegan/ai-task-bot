"""Application settings. Mirrored in .env.example and docker-compose.yml."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = ""
    database_url: str = "postgresql+asyncpg://app:app@postgres:5432/app"
    redis_url: str = "redis://redis:6379/0"

    transcriber: Literal["local", "openai_compatible", "fake"] = "local"
    whisper_model: str = "small"
    whisper_compute_type: str = "int8"
    whisper_language: str = ""  # empty = auto-detect
    # Primes the decoder with task-like phrasing so homophones resolve the right way
    # ("buy butter" rather than "bye butter"). Empty disables it.
    whisper_initial_prompt: str = (
        "To-do list: buy milk, buy bread, call the dentist, pay the electricity bill, "
        "book a meeting with Anna, send the report, fix the login bug."
    )

    openai_compat_base_url: str = ""
    openai_compat_api_key: str = ""
    openai_compat_model: str = ""

    max_voice_bytes: int = 20 * 1024 * 1024  # Telegram bot download limit
    max_voice_seconds: int = 300  # longer notes are rejected up front
    transcribe_timeout_seconds: int = 600  # download + transcription; owned by the job itself
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"  # comma-separated

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
