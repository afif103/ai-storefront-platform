"""Celery tasks for order and donation notifications."""

import asyncio
import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.donation import Donation
from app.models.notification_preference import NotificationPreference
from app.models.order import Order
from app.models.tenant import Tenant
from app.services.notifications.email_sender import send_email
from app.services.notifications.telegram_sender import send_telegram
from app.services.notifications.templates import (
    format_donation_notification,
    format_order_notification,
)
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _process_order_notification(
    session: AsyncSession, tenant_id: str, order_id: str
) -> None:
    """Core order notification logic. Accepts a session for testability."""
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )

    # Fetch preferences
    result = await session.execute(
        select(NotificationPreference).where(
            NotificationPreference.tenant_id == tenant_id
        )
    )
    prefs = result.scalar_one_or_none()
    if prefs is None or (not prefs.email_enabled and not prefs.telegram_enabled):
        logger.info(
            "Notifications disabled for tenant=%s, skipping order=%s",
            tenant_id,
            order_id,
        )
        return

    # Fetch order
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        logger.warning("Order %s not found for notification", order_id)
        return

    # Fetch tenant name
    result = await session.execute(
        select(Tenant.name).where(Tenant.id == tenant_id)
    )
    tenant_name = result.scalar_one()

    # Format message
    subject, body = format_order_notification(
        tenant_name=tenant_name,
        order_number=order.order_number,
        total=str(order.total_amount),
        currency=order.currency,
        customer_name=order.customer_name,
    )

    # Send email
    if prefs.email_enabled:
        if order.customer_email:
            send_email(to=order.customer_email, subject=subject, body=body)
        else:
            logger.info(
                "Order %s has no customer_email, skipping email notification",
                order_id,
            )

    # Send Telegram
    if prefs.telegram_enabled:
        if not prefs.telegram_chat_id:
            logger.warning(
                "Telegram enabled but chat_id missing for tenant=%s, skipping",
                tenant_id,
            )
        else:
            bot_token = settings.TELEGRAM_BOT_TOKEN
            send_telegram(
                bot_token=bot_token, chat_id=prefs.telegram_chat_id, text=body
            )


async def _process_donation_notification(
    session: AsyncSession, tenant_id: str, donation_id: str
) -> None:
    """Core donation notification logic. Accepts a session for testability."""
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )

    # Fetch preferences
    result = await session.execute(
        select(NotificationPreference).where(
            NotificationPreference.tenant_id == tenant_id
        )
    )
    prefs = result.scalar_one_or_none()
    if prefs is None or (not prefs.email_enabled and not prefs.telegram_enabled):
        logger.info(
            "Notifications disabled for tenant=%s, skipping donation=%s",
            tenant_id,
            donation_id,
        )
        return

    # Fetch donation
    result = await session.execute(
        select(Donation).where(Donation.id == donation_id)
    )
    donation = result.scalar_one_or_none()
    if donation is None:
        logger.warning("Donation %s not found for notification", donation_id)
        return

    # Fetch tenant name
    result = await session.execute(
        select(Tenant.name).where(Tenant.id == tenant_id)
    )
    tenant_name = result.scalar_one()

    # Format message
    subject, body = format_donation_notification(
        tenant_name=tenant_name,
        donation_number=donation.donation_number,
        amount=str(donation.amount),
        currency=donation.currency,
        donor_name=donation.donor_name,
    )

    # Send email
    if prefs.email_enabled:
        if donation.donor_email:
            send_email(to=donation.donor_email, subject=subject, body=body)
        else:
            logger.info(
                "Donation %s has no donor_email, skipping email notification",
                donation_id,
            )

    # Send Telegram
    if prefs.telegram_enabled:
        if not prefs.telegram_chat_id:
            logger.warning(
                "Telegram enabled but chat_id missing for tenant=%s, skipping",
                tenant_id,
            )
        else:
            bot_token = settings.TELEGRAM_BOT_TOKEN
            send_telegram(
                bot_token=bot_token, chat_id=prefs.telegram_chat_id, text=body
            )


@celery_app.task(name="send_order_notification", ignore_result=True)
def send_order_notification(tenant_id: str, order_id: str) -> None:
    """Notify tenant about a new order (email + Telegram if enabled)."""

    async def _run() -> None:
        async with async_session_factory() as session:
            await _process_order_notification(session, tenant_id, order_id)

    asyncio.run(_run())


@celery_app.task(name="send_donation_notification", ignore_result=True)
def send_donation_notification(tenant_id: str, donation_id: str) -> None:
    """Notify tenant about a new donation (email + Telegram if enabled)."""

    async def _run() -> None:
        async with async_session_factory() as session:
            await _process_donation_notification(session, tenant_id, donation_id)

    asyncio.run(_run())
