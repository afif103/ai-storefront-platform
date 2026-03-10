"""Telegram Bot API sender."""

import logging

import httpx

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org"
_TIMEOUT = 10  # seconds


def send_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    """Send a Telegram message. Returns True on success, False on failure.

    Never raises — all errors are caught and logged.
    """
    if not bot_token:
        logger.warning("Telegram send skipped: bot_token is empty")
        return False

    if not chat_id:
        logger.warning("Telegram send skipped: chat_id is empty")
        return False

    url = f"{_TELEGRAM_API}/bot{bot_token}/sendMessage"
    try:
        resp = httpx.post(
            url,
            json={"chat_id": chat_id, "text": text},
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            logger.info("Telegram message sent chat_id=%s", chat_id)
            return True
        logger.warning(
            "Telegram API error status=%d body=%s",
            resp.status_code,
            resp.text[:200],
        )
        return False
    except httpx.HTTPError:
        logger.exception("Telegram send failed chat_id=%s", chat_id)
        return False
