"""Shared schema types: pagination, error responses, bulk operations."""

import uuid
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


class ErrorResponse(BaseModel):
    type: str
    title: str
    status: int
    detail: str | dict | list
    instance: str


class BulkDeleteRequest(BaseModel):
    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)


class BulkDeleteResponse(BaseModel):
    deleted: int
