# app/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path
from typing import Literal


class Settings(BaseSettings):
    # ==========
    # Core App
    # ==========
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    app_name: str = "UpDrive"
    app_version: str = "0.1.0"

    # ==========
    # Security
    # ==========
    secret_key: str = Field(..., description="JWT secret key")
    access_token_expire_minutes: int = 1440
    jwt_algorithm: str = "HS256"

    # ==========
    # Database
    # ==========
    database_url: str = Field(..., description="Database connection string")

    # ==========
    # Storage
    # ==========
    storage_path: Path = Path("./data")
    max_upload_size_mb: int = 500

    # ==========
    # CORS
    # ==========
    cors_allow_origins: str = "*"  # comma-separated list in prod
    cors_allow_credentials: bool = True
    cors_allow_methods: str = "*"
    cors_allow_headers: str = "*"

    # ==========
    # Rate Limiting (future use)
    # ==========
    enable_rate_limiting: bool = False
    requests_per_minute: int = 120

    # ==========
    # Logging
    # ==========
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    model_config = SettingsConfigDict(
        env_prefix="UPDRIVE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()