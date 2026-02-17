"""
Configuration settings for the AI Product Curator application.
Uses pydantic-settings to load from .env file automatically.
"""

import os
import secrets
import logging
from typing import List
from pathlib import Path

_CONFIG_DIR = Path(__file__).parent
_PROJECT_ROOT = _CONFIG_DIR.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

from dotenv import load_dotenv
load_dotenv(_ENV_FILE, override=True)

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # Database Configuration
    DATABASE_URL: str = Field(default="")
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=5432)
    DB_NAME: str = Field(default="ecommerce_ai")
    DB_USER: str = Field(default="")
    DB_PASSWORD: str = Field(default="")

    # Database Pool Configuration
    DB_POOL_SIZE: int = Field(default=10)
    DB_POOL_MAX_OVERFLOW: int = Field(default=20)
    DB_POOL_TIMEOUT: int = Field(default=30)
    DB_POOL_RECYCLE: int = Field(default=1800)

    # Groq API (Primary)
    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL: str = Field(default="meta-llama/llama-4-scout-17b-16e-instruct")

    # HuggingFace API (Fallback - OpenAI-compatible router)
    HUGGINGFACE_API_KEY: str = Field(default="")
    HUGGINGFACE_MODEL: str = Field(default="meta-llama/Llama-3.1-8B-Instruct:novita")

    # API Configuration
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    API_RELOAD: bool = Field(default=True)

    # CORS Origins
    CORS_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]
    )

    # Scraping Configuration
    REQUEST_TIMEOUT: int = Field(default=30)

    # Application Settings
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    DEBUG: bool = Field(default=True)

    # JWT Configuration
    JWT_SECRET_KEY: str = Field(default="")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode="after")
    def validate_critical_settings(self):
        # JWT Secret: require in production, auto-generate in dev
        if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY in (
            "change-this-secret-key-in-production",
            "change-this-to-a-secure-random-string-in-production",
        ):
            if self.ENVIRONMENT == "production":
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a strong random value in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
            self.JWT_SECRET_KEY = secrets.token_urlsafe(32)
            logger.warning(
                "JWT_SECRET_KEY not set — using auto-generated key. "
                "Tokens will be invalidated on restart. Set JWT_SECRET_KEY in .env for persistence."
            )

        # DATABASE_URL: require in production
        if not self.DATABASE_URL:
            if self.ENVIRONMENT == "production":
                raise ValueError("DATABASE_URL must be set in production.")
            logger.warning("DATABASE_URL not set — database features will be unavailable.")

        return self


settings = Settings()
