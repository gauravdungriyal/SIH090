from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    gemini_transcription_model: str = "gemini-3.5-transcribe"
    gemini_text_model: str = "gemini-3.5-flash-lite"
    gemini_audio_fallback_model: str = "gemini-3.8-flash"
    gemini_text_timeout_seconds: float = 12
    database_url: str = "sqlite:///./catalogue.db"
    max_audio_size_mb: int = 10
    max_audio_duration_seconds: int = 60
    request_timeout_seconds: float = 30
    cors_origins: str = "http://localhost:3000"
    default_currency_inr: bool = False
    rate_limit_per_minute: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
