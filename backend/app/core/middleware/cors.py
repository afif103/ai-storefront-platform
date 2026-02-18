"""Dynamic CORS origin validation configuration."""

import re

from app.core.config import settings

# Production pattern: yourdomain.com and all subdomains
ALLOWED_ORIGIN_PATTERN = re.compile(r"^https://([a-z0-9-]+\.)?yourdomain\.com$")


def get_cors_config() -> dict:
    """Return CORS middleware kwargs for FastAPI."""
    return {
        "allow_origins": settings.allowed_origins_list,
        "allow_credentials": False,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": [
            "Authorization",
            "Content-Type",
            "X-Request-Id",
            "X-Tenant-Id",
        ],
    }


def validate_origin(origin: str) -> bool:
    """Validate an origin against the allowlist (for production use)."""
    if origin in settings.allowed_origins_list:
        return True
    return settings.ENVIRONMENT != "development" and bool(ALLOWED_ORIGIN_PATTERN.match(origin))
