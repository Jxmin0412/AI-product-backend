"""
Configuration settings for the AI Product Curator application.
Uses pydantic-settings to load from .env file automatically.
"""

import os
import logging
from typing import List
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
_logger.info(f"GROQ_API_KEY in env: {bool(os.getenv('GROQ_API_KEY'))}")

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


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

    # Groq API (Preferred - Fast & Free)
    GROQ_API_KEY: str = Field(default="")
    GROQ_MODEL: str = Field(default="llama-3.3-70b-versatile")

    # Hugging Face API (Fallback)
    HUGGINGFACE_API_KEY: str = Field(default="")
    HUGGINGFACE_MODEL: str = Field(default="microsoft/Phi-3-mini-4k-instruct")

    # Redis Configuration
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Celery Configuration
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0")

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
    SCRAPING_DELAY: int = Field(default=2)
    MAX_RETRIES: int = Field(default=3)
    REQUEST_TIMEOUT: int = Field(default=30)

    # Application Settings
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    DEBUG: bool = Field(default=True)

    # JWT Configuration
    JWT_SECRET_KEY: str = Field(default="change-this-secret-key-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Create global settings instance
settings = Settings()

# Debug: print loaded values on import
_logger.info(f"Settings initialized:")
_logger.info(f"  GROQ_API_KEY loaded: {bool(settings.GROQ_API_KEY)} (length: {len(settings.GROQ_API_KEY) if settings.GROQ_API_KEY else 0})")
_logger.info(f"  GROQ_MODEL: {settings.GROQ_MODEL}")
