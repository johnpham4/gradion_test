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
    
    # Gemini model configuration
    # Primary text model (Free Tier available)
    GEMINI_TEXT_MODEL: str = "gemini-2.5-flash"
    
    # Image models (PAID-ONLY as of 2026 - Free Tier no longer available)
    # NOTE: Image generation requires billing/usage to work
    # Models from Nano Banana family - see: https://ai.google.dev/gemini-api/docs/interactions/image-generation
    GEMINI_IMAGE_MODEL: str = "gemini-2.5-flash-image"  # Legacy but still supported
    GEMINI_IMAGE_MODEL_ALTERNATIVE: str = "gemini-3.1-flash-lite-image"  # Requires billing


settings = Settings()