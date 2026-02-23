"""Public-facing storefront config response (no tenant_id, no raw S3 keys)."""

from pydantic import BaseModel


class PublicStorefrontConfigResponse(BaseModel):
    hero_text: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    logo_url: str | None = None
