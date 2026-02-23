"""Salted IP hashing for privacy-safe visit tracking."""

import hashlib

from app.core.config import settings


def hash_ip(ip: str | None) -> str | None:
    """Return salted SHA-256 hex digest of the IP, or None if no IP."""
    if not ip:
        return None
    return hashlib.sha256(f"{settings.IP_HASH_SALT}:{ip}".encode()).hexdigest()
