# Filename: webdrive/config.py
from typing import Optional
import os

# Try to import app.config.settings if available (but don't crash if it fails).
try:
    # app.config may try to read environment/.env — if that raises during import,
    # we catch and ignore and fall back to environment variables below.
    from app.config import settings as backend_settings  # type: ignore

    API_URL = getattr(backend_settings, "api_url", None) if hasattr(backend_settings, "api_url") else None
    APP_NAME = getattr(backend_settings, "app_name", "UpDrive")
    APP_VERSION = getattr(backend_settings, "app_version", "0.1.0")
except Exception:
    backend_settings = None
    API_URL = None
    APP_NAME = "UpDrive"
    APP_VERSION = "0.1.0"

# Environment overrides (highest precedence)
API_URL = os.getenv("WEBDRIVE_API_URL") or API_URL or os.getenv("UPDRIVE_API_URL") or os.getenv("UPDRIVE_BASE_URL") or "http://localhost:8000"
FRONTEND_PORT = int(os.getenv("WEBDRIVE_PORT", "8080"))
APP_NAME = os.getenv("WEBDRIVE_APP_NAME", APP_NAME)
APP_VERSION = os.getenv("WEBDRIVE_APP_VERSION", APP_VERSION)