"""POS order request schemas."""

from pydantic import BaseModel, Field

from app.schemas.order import OrderItemRequest


class PosOrderCreateRequest(BaseModel):
    items: list[OrderItemRequest] = Field(..., min_length=1)
    customer_name: str | None = Field(None, max_length=255)
