from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

_ROOT = Path(__file__).resolve().parents[3]
_BACKEND = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    PROJECT_NAME: str = "JEEVAN"
    DATABASE_URL: str = ""
    SUPABASE_URL: str | None = None
    VITE_SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None
    SUPABASE_ANON_KEY: str | None = None
    VITE_SUPABASE_ANON_KEY: str | None = None
    STAFF_BOOTSTRAP_EMAILS: str = ""
    CORS_ORIGINS: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    GOOGLE_MAPS_API_KEY: str | None = None
    TOMTOM_API_KEY: str | None = None
    MSG91_AUTH_KEY: str | None = None
    MSG91_SENDER: str = "JEEVAN"
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None
    TWILIO_FROM: str | None = None
    TWILIO_WHATSAPP_FROM: str | None = None
    NVIDIA_API_KEY: str | None = None
    NVIDIA_MODEL: str = "nvidia/nemotron-mini-4b-instruct"
    NVIDIA_MODEL_FALLBACKS: str = "meta/llama-3.1-8b-instruct,nvidia/nemotron-3-nano-30b-a3b"
    NVIDIA_VISION_MODEL: str = "microsoft/phi-3-vision-128k-instruct"
    NVIDIA_VISION_MODEL_FALLBACKS: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    GEMINI_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.0-flash"
    TAVUS_API_KEY: str | None = None
    TAVUS_REPLICA_ID: str | None = None
    TAVUS_PERSONA_ID: str | None = None
    TAVUS_PAL_ID: str | None = None
    TAVUS_FACE_ID: str | None = None
    TAVUS_CALLBACK_URL: str | None = None

    @model_validator(mode="after")
    def _alias_vite_supabase(self):
        if not self.SUPABASE_URL and self.VITE_SUPABASE_URL:
            self.SUPABASE_URL = self.VITE_SUPABASE_URL
        if not self.SUPABASE_ANON_KEY and self.VITE_SUPABASE_ANON_KEY:
            self.SUPABASE_ANON_KEY = self.VITE_SUPABASE_ANON_KEY
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Prefer project .env over a stale NVIDIA_API_KEY inherited by the shell.
        return (init_settings, dotenv_settings, env_settings, file_secret_settings)

    model_config = SettingsConfigDict(
        env_file=(
            str(_ROOT / ".env"),
            str(_BACKEND / ".env"),
            ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
