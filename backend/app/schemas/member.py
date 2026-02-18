"""Member/invite request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class MemberInvite(BaseModel):
    email: EmailStr
    role: str = Field(default="member", pattern=r"^(admin|member)$")


class MemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    email: str | None = None
    full_name: str | None = None
    role: str
    status: str
    invited_at: datetime | None = None
    joined_at: datetime | None = None

    model_config = {"from_attributes": True}


class MemberUpdate(BaseModel):
    role: str | None = Field(None, pattern=r"^(owner|admin|member)$")
