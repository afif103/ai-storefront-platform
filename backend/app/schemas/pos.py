"""POS order request schemas."""

from pydantic import BaseModel, Field, field_validator

from app.schemas.order import OrderItemRequest
from app.schemas.payment import normalize_optional_payment_method


class PosOrderCreateRequest(BaseModel):
    items: list[OrderItemRequest] = Field(..., min_length=1)
    customer_name: str | None = Field(None, max_length=255)
    payment_method: str | None = None

    @field_validator("payment_method")
    @classmethod
    def _normalize_payment_method(cls, v: str | None) -> str | None:
        return normalize_optional_payment_method(v)
