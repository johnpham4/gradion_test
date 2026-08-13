from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # Ignore extra env vars like NEXT_PUBLIC_*
    )
    
    BACKEND_HOST: str = "localhost"  # Back to localhost for Windows
    BACKEND_PORT: int = 8000
    GEMINI_API_KEY: str = ""
    
    # Gemini model configuration
    # Primary text model (matches the reference notebook default)
    GEMINI_TEXT_MODEL: str = "gemini-3.6-flash"

    # Image models (Nano Banana family - matches the reference notebook default)
    # See: https://ai.google.dev/gemini-api/docs/interactions/image-generation
    GEMINI_IMAGE_MODEL: str = "gemini-3.1-flash-lite-image"
    GEMINI_IMAGE_MODEL_ALTERNATIVE: str = "gemini-2.5-flash-image"

    # Image provider configuration
    # Options: "mock", "gemini"
    # - mock: Generates placeholder images locally (no API calls) - DEFAULT
    #   (Gemini image models are paid-only as of 2026: gemini-3.1-flash-lite-image
    #   has no free tier. Text model gemini-3.6-flash remains free.)
    # - gemini: Uses Gemini image generation (real Nano Banana calls, billing required)
    IMAGE_PROVIDER: str = "mock"
    
    # Mock image configuration
    MOCK_IMAGE_OUTPUT_DIR: str = "data/mock_images"


settings = Settings()