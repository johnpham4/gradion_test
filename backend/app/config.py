from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    BACKEND_HOST: str = "localhost"
    BACKEND_PORT: int = 8000
    GEMINI_API_KEY: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()