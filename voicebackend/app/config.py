from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bhashini_user_id: str = ""
    bhashini_api_key: str = ""
    bhashini_pipeline_id: str = ""
    bhashini_asr_service_id: str = "bhashini/ai4bharat/conformer-multilingual-asr"
    bhashini_translation_service_id: str = "ai4bharat/indictrans-v2-all-gpu--t4"
    bhashini_transliteration_service_id: str = ""
    bhashini_config_url: str = (
        "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
    )
    bhashini_compute_url: str = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
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
