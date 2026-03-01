"""Aggregate all v1 sub-routers."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.categories import router as categories_router
from app.api.v1.health import router as health_router
from app.api.v1.media import router as media_router
from app.api.v1.members import router as members_router
from app.api.v1.products import router as products_router
from app.api.v1.public_storefront import router as public_storefront_router
from app.api.v1.status_transitions import router as status_transitions_router
from app.api.v1.storefront_config import router as storefront_config_router
from app.api.v1.tenants import router as tenants_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router, tags=["health"])
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(tenants_router, prefix="/tenants", tags=["tenants"])
api_v1_router.include_router(members_router, prefix="/tenants/me/members", tags=["members"])
api_v1_router.include_router(
    categories_router, prefix="/tenants/me/categories", tags=["categories"]
)
api_v1_router.include_router(products_router, prefix="/tenants/me/products", tags=["products"])
api_v1_router.include_router(media_router, prefix="/tenants/me/media", tags=["media"])
api_v1_router.include_router(
    storefront_config_router, prefix="/tenants/me/storefront", tags=["storefront-config"]
)
api_v1_router.include_router(
    status_transitions_router, prefix="/tenants/me", tags=["status-transitions"]
)
api_v1_router.include_router(public_storefront_router, prefix="/storefront", tags=["storefront"])
