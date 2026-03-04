"""Storefront AI chat request/response schemas."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class StorefrontAIChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=2000)


class StorefrontAIChatUsage(BaseModel):
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal


class StorefrontAIChatResponse(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    usage: StorefrontAIChatUsage
