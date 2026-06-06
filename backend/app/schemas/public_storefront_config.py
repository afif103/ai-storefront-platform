"""Public-facing storefront config response (no tenant_id, no raw S3 keys)."""

from pydantic import BaseModel

from app.schemas.shipping import PublicShippingMethod


class PublicStorefrontConfigResponse(BaseModel):
    hero_text: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    logo_url: str | None = None
    payment_methods: list[str] | None = None
    shipping_methods: list[PublicShippingMethod] | None = None
