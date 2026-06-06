"""Shipping method config + resolution schemas."""

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

MAX_SHIPPING_METHODS = 50


class ShippingMethodError(Exception):
    """Raised when a shipping_method_id cannot be resolved against tenant config.

    Endpoints map this to HTTP 422.
    """

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class ShippingMethod(BaseModel):
    """A tenant-configured flat-fee delivery method (stored in storefront_config.shipping)."""

    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=120)
    fee: Decimal = Field(..., ge=0, max_digits=12, decimal_places=3)
    active: bool = True

    @field_validator("id", "name")
    @classmethod
    def _require_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class ShippingConfig(BaseModel):
    """Tenant shipping configuration: a flat list of delivery methods."""

    methods: list[ShippingMethod] = Field(default_factory=list, max_length=MAX_SHIPPING_METHODS)

    @field_validator("methods")
    @classmethod
    def _unique_ids(cls, v: list[ShippingMethod]) -> list[ShippingMethod]:
        ids = [m.id for m in v]
        if len(ids) != len(set(ids)):
            raise ValueError("shipping method ids must be unique")
        return v


class PublicShippingMethod(BaseModel):
    """Customer-facing delivery method (active only; no active flag exposed)."""

    id: str
    name: str
    fee: Decimal


def resolve_shipping_method(
    config: ShippingConfig | None, method_id: str | None
) -> tuple[str, Decimal]:
    """Resolve a shipping_method_id against tenant shipping config.

    Returns (method_name, fee). Raises ShippingMethodError (HTTP 422) when no
    methods are configured, the id is unknown, or the method is inactive.
    """
    if config is None or not config.methods:
        raise ShippingMethodError("No shipping methods are configured")
    for method in config.methods:
        if method.id == method_id:
            if not method.active:
                raise ShippingMethodError("Selected shipping method is not available")
            return method.name, method.fee
    raise ShippingMethodError("Shipping method not found")
