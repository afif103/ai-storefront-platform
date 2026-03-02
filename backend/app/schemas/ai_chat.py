"""AI chat request/response schemas."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class AIChatUsage(BaseModel):
    tokens_in: int
    tokens_out: int
    cost_usd: Decimal


class AIChatResponse(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    usage: AIChatUsage
