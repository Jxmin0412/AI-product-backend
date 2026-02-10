"""
Configuration settings for the AI Product Curator application.
Uses pydantic-settings to load from .env file automatically.
"""

import logging
from pathlib import Path

# Get the directory containing this file
_CONFIG_DIR = Path(__file__).parent
_PROJECT_ROOT = _CONFIG_DIR.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

# Explicitly load .env file BEFORE importing pydantic-settings
# This ensures environment variables are set
from dotenv import load_dotenv
load_dotenv(_ENV_FILE, override=True)

_logger = logging.getLogger(__name__)
_logger.info(f"Loaded .env from: {_ENV_FILE}")

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # Database Configuration
    DATABASE_URL: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/ecommerce_ai"
    )
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=5432)
    DB_NAME: str = Field(default="ecommerce_ai")
    DB_USER: str = Field(default="postgres")
    DB_PASSWORD: str = Field(default="postgres")

    # Database Pool Configuration
    DB_POOL_SIZE: int = Field(default=10)
    DB_POOL_MAX_OVERFLOW: int = Field(default=20)
    DB_POOL_TIMEOUT: int = Field(default=30)
    DB_POOL_RECYCLE: int = Field(default=1800)
    DB_POOL_PRE_PING: bool = Field(default=True)
    DB_ECHO_POOL: bool = Field(default=False)

    # LLM Configuration (OpenAI-compatible — works with HuggingFace, Groq, etc.)
    LLM_API_KEY: str = Field(default="")
    LLM_API_URL: str = Field(default="https://router.huggingface.co/v1/chat/completions")
    LLM_MODEL: str = Field(default="meta-llama/Llama-3.1-8B-Instruct:novita")

    # Redis Configuration
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Celery Configuration
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0")

    # API Configuration
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8001)
    API_RELOAD: bool = Field(default=True)

    # Scraping Configuration
    SCRAPING_DELAY: int = Field(default=2)
    MAX_RETRIES: int = Field(default=3)
    REQUEST_TIMEOUT: int = Field(default=30)

    # LLM Optimization
    USE_LLM_QUERY_EXTRACTION: bool = Field(default=False)
    USE_BATCH_RECOMMENDATIONS: bool = Field(default=True)

    # LLM Rate Limiting
    LLM_RATE_LIMIT: int = Field(default=20)
    LLM_BURST_LIMIT: int = Field(default=5)

    # Application Settings
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    DEBUG: bool = Field(default=True)

    # JWT Configuration
    JWT_SECRET_KEY: str = Field(default="")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    @model_validator(mode="after")
    def validate_jwt_secret(self) -> "Settings":
        if not self.JWT_SECRET_KEY:
            if self.ENVIRONMENT == "production":
                raise ValueError(
                    "JWT_SECRET_KEY must be set via environment variable in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )
            else:
                _logger.warning(
                    "JWT_SECRET_KEY not set — using an insecure default for development. "
                    "Set JWT_SECRET_KEY in your .env file."
                )
                self.JWT_SECRET_KEY = "insecure-dev-only-key-do-not-use-in-production"
        return self

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Create global settings instance
settings = Settings()

_logger.info(f"Settings initialized: LLM_API_URL={settings.LLM_API_URL}, LLM_MODEL={settings.LLM_MODEL}")
