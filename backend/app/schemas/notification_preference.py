"""Notification preferences request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, model_validator


class NotificationPreferencesUpdate(BaseModel):
    """PUT body — all fields optional (patch semantics)."""

    email_enabled: bool | None = None
    telegram_enabled: bool | None = None
    telegram_chat_id: str | None = None

    @model_validator(mode="after")
    def _telegram_chat_id_required_when_enabled(self) -> "NotificationPreferencesUpdate":
        if self.telegram_enabled is True and not self.telegram_chat_id:
            raise ValueError(
                "telegram_chat_id is required when enabling Telegram notifications"
            )
        return self


class NotificationPreferencesResponse(BaseModel):
    email_enabled: bool
    telegram_enabled: bool
    telegram_chat_id: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
