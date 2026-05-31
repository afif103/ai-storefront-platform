"""Payment method catalog + config schemas."""

from pydantic import BaseModel, Field, field_validator

PAYMENT_METHOD_CATALOG = ("cash", "knet", "bank_transfer", "cod", "manual")
DEFAULT_POS_PAYMENT_METHODS = ["cash"]


def normalize_optional_payment_method(v: str | None) -> str | None:
    if v is None:
        return None
    stripped = v.strip()
    if not stripped:
        return None
    if stripped not in PAYMENT_METHOD_CATALOG:
        raise ValueError(f"Unknown payment method: {stripped}")
    return stripped


class PaymentMethodsConfig(BaseModel):
    pos: list[str] = Field(default_factory=list)
    online: list[str] = Field(default_factory=list)

    @field_validator("pos", "online")
    @classmethod
    def _validate_codes(cls, v: list[str]) -> list[str]:
        for code in v:
            if code not in PAYMENT_METHOD_CATALOG:
                raise ValueError(f"Unknown payment method: {code}")
        return v


class PosPaymentMethodsResponse(BaseModel):
    payment_methods: list[str]
