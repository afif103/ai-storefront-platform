"""Aggregate all v1 sub-routers."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.members import router as members_router
from app.api.v1.tenants import router as tenants_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router, tags=["health"])
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(tenants_router, prefix="/tenants", tags=["tenants"])
api_v1_router.include_router(members_router, prefix="/tenants/me/members", tags=["members"])
