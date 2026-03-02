"""Dashboard AI assistant chat endpoint.

POST /tenants/me/ai/chat — authenticated, member+ role.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user, get_db_with_tenant, require_role
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.ai_chat import AIChatRequest, AIChatResponse, AIChatUsage
from app.services.ai_gateway import AIGatewayError, handle_chat
from app.services.ai_provider import get_provider

router = APIRouter()


@router.post("/ai/chat", response_model=AIChatResponse)
async def ai_chat(
    body: AIChatRequest,
    user: User = Depends(get_current_user),
    db_tenant: tuple[AsyncSession, uuid.UUID] = Depends(get_db_with_tenant),
) -> AIChatResponse:
    """Send a message to the AI assistant."""
    db, tenant_id = db_tenant
    await require_role("member", db, tenant_id, user)

    # Load tenant with plan eagerly for quota check
    result = await db.execute(
        select(Tenant).options(selectinload(Tenant.plan)).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=500, detail="Tenant not found")

    provider = get_provider()

    try:
        chat_result = await handle_chat(db, tenant, user.id, body.message, provider)
    except AIGatewayError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"message": e.detail, "type": e.error_type},
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={"message": "AI provider error", "type": "provider_error"},
        ) from e

    return AIChatResponse(
        conversation_id=chat_result.conversation_id,
        reply=chat_result.reply,
        usage=AIChatUsage(
            tokens_in=chat_result.tokens_in,
            tokens_out=chat_result.tokens_out,
            cost_usd=chat_result.cost_usd,
        ),
    )
