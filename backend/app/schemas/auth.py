"""Auth schemas."""

from pydantic import BaseModel


class RefreshResponse(BaseModel):
    access_token: str
