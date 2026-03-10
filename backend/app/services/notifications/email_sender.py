"""Email sending via AWS SES (dev mode: log only)."""

import logging

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns True on success, False on failure.

    In development mode, logs the email instead of sending via SES.
    Never raises — all errors are caught and logged.
    """
    if settings.ENVIRONMENT == "development":
        logger.info(
            "DEV email | to=%s subject=%s body_len=%d",
            to,
            subject,
            len(body),
        )
        return True

    try:
        ses = boto3.client("ses", region_name=settings.SES_REGION)
        ses.send_email(
            Source=settings.SES_SENDER_EMAIL,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        logger.info("Email sent to=%s subject=%s", to, subject)
        return True
    except ClientError:
        logger.exception("SES send_email failed to=%s", to)
        return False
