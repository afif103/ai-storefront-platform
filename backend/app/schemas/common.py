"""Shared schema types: pagination, error responses."""

from typing import Generic, TypeVar

from pydantic import BaseModel

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
