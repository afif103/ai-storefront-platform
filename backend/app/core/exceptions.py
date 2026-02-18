"""RFC 7807 Problem Details error handling."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ProblemDetailError(Exception):
    """Raise for RFC 7807 problem+json responses."""

    def __init__(
        self,
        status: int,
        title: str,
        detail: str,
        error_type: str | None = None,
    ):
        self.status = status
        self.title = title
        self.detail = detail
        self.error_type = error_type or "about:blank"


async def problem_detail_handler(request: Request, exc: ProblemDetailError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status,
        content={
            "type": exc.error_type,
            "title": exc.title,
            "status": exc.status,
            "detail": exc.detail,
            "instance": str(request.url.path),
        },
        media_type="application/problem+json",
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "type": "about:blank",
            "title": exc.detail if isinstance(exc.detail, str) else "Error",
            "status": exc.status_code,
            "detail": exc.detail,
            "instance": str(request.url.path),
        },
        media_type="application/problem+json",
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "type": "about:blank",
            "title": "Validation Error",
            "status": 422,
            "detail": exc.errors(),
            "instance": str(request.url.path),
        },
        media_type="application/problem+json",
    )
