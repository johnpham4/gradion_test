from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # Ignore extra env vars like NEXT_PUBLIC_*
    )
    
    BACKEND_HOST: str = "localhost"
    BACKEND_PORT: int = 8000
    GEMINI_API_KEY: str = ""


settings = Settings()