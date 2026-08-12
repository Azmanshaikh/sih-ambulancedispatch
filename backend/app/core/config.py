from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "JEEVAN"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/jeevan"
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "supersecretjwtkey123"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    GOOGLE_MAPS_API_KEY: str | None = None
    TOMTOM_API_KEY: str | None = None
    NVIDIA_API_KEY: str | None = None
    NVIDIA_MODEL: str = "nvidia/llama-3.1-nemotron-nano-8b-v1"
    NVIDIA_VISION_MODEL: str = "microsoft/phi-3-vision-128k-instruct"
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

    class Config:
        env_file = "../.env"
        extra = "ignore"

settings = Settings()
