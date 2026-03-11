"""AI provider abstraction layer.

Protocol + concrete providers. Default is OpenAI; Anthropic kept as optional
fallback. All AI calls go through this module; route handlers and the gateway
never import provider SDKs directly.
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


class OpenAIProvider:
    """OpenAI-compatible provider. Works with OpenAI, Groq, and other
    services that expose the OpenAI chat completions API."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        import openai

        self._client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 1024,
    ) -> AIResponse:
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=messages,
        )

        choice = response.choices[0]
        usage = response.usage

        return AIResponse(
            content=choice.message.content or "",
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
            model=self._model,
        )


_GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def get_provider() -> AIProvider:
    """Factory: return the configured provider instance.

    Supported: "openai" (default), "groq", "anthropic".
    """
    provider_name = settings.AI_PROVIDER.lower()
    if provider_name == "anthropic":
        return AnthropicProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
        )
    if provider_name == "openai":
        return OpenAIProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
        )
    if provider_name == "groq":
        return OpenAIProvider(
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
            base_url=_GROQ_BASE_URL,
        )
    raise ValueError(f"Unknown AI provider: {provider_name}")
