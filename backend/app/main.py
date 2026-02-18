"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_v1_router
from app.core.exceptions import (
    ProblemDetailError,
    http_exception_handler,
    problem_detail_handler,
    validation_exception_handler,
)
from app.core.middleware.cors import get_cors_config
from app.core.middleware.request_id import RequestIdMiddleware

app = FastAPI(
    title="Multi-Tenant SaaS API",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Middleware (last added = first executed)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(CORSMiddleware, **get_cors_config())

# Exception handlers (RFC 7807)
app.add_exception_handler(ProblemDetailError, problem_detail_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Routes
app.include_router(api_v1_router, prefix="/api/v1")
