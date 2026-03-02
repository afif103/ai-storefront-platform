"""AI provider abstraction layer.

Protocol + concrete AnthropicProvider. All AI calls go through this module;
route handlers and the gateway never import provider SDKs directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings


@dataclass(frozen=True)
class AIResponse:
    """Standardised response from any AI provider."""

    content: str
    tokens_in: int
    tokens_out: int
    model: str


class AIProvider(Protocol):
    """Interface that every provider implementation must satisfy."""

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 1024,
    ) -> AIResponse: ...


class AnthropicProvider:
    """Anthropic Claude provider using the official SDK."""

    def __init__(self, api_key: str, model: str) -> None:
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 1024,
    ) -> AIResponse:
        # Separate system message from conversation turns
        system_text = ""
        conversation: list[dict[str, str]] = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                conversation.append(msg)

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_text or None,
            messages=conversation,
        )

        return AIResponse(
            content=response.content[0].text,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            model=self._model,
        )


def get_provider() -> AIProvider:
    """Factory: return the configured provider instance."""
    provider_name = settings.AI_PROVIDER.lower()
    if provider_name == "anthropic":
        return AnthropicProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
        )
    raise ValueError(f"Unknown AI provider: {provider_name}")
