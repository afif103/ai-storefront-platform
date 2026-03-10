"""Platform admin request/response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class AdminTenantListItem(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    member_count: int

    model_config = {"from_attributes": True}


class AdminTenantActionResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool

    model_config = {"from_attributes": True}
