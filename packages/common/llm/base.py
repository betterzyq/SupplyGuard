"""Base LLM provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from packages.common.llm.usage import estimate_cost, normalize_token_usage


@dataclass
class ChatResult:
    content: str
    token_usage: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    provider: str | None = None


@dataclass(frozen=True)
class ModelInfo:
    provider: str
    model: str
    base_url: str


class LLMProviderError(Exception):
    """Normalized LLM provider error."""

    def __init__(self, message: str, *, code: str = "llm_error") -> None:
        super().__init__(message)
        self.code = code


class BaseLLMProvider(ABC):
    provider_name: str = "base"
    model_name: str = ""

    @abstractmethod
    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> ChatResult:
        """Send chat completion request."""

    async def stream_chat(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> AsyncIterator[str]:
        """Streaming chat (reserved for future use)."""
        raise NotImplementedError(f"{self.provider_name} does not support stream_chat yet")

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Return {status: ok|error, ...}."""

    @abstractmethod
    def get_model_info(self) -> ModelInfo:
        """Return provider/model metadata."""

    def estimate_cost(self, token_usage: dict[str, Any] | None) -> float:
        return estimate_cost(token_usage, model=self.model_name)


class OpenAICompatibleProvider(BaseLLMProvider):
    """Shared OpenAI-compatible chat.completions implementation."""

    def __init__(
        self,
        *,
        provider_name: str,
        model: str,
        api_key: str,
        base_url: str,
        timeout: float,
        max_retries: int,
    ) -> None:
        self.provider_name = provider_name
        self.model_name = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=self._base_url,
            timeout=timeout,
        )

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(provider=self.provider_name, model=self.model_name, base_url=self._base_url)

    def _retry_decorator(self):
        return retry(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((APIConnectionError, APITimeoutError, APIStatusError)),
            reraise=True,
        )

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> ChatResult:
        @self._retry_decorator()
        async def _call() -> ChatResult:
            try:
                response = await self._client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    **kwargs,
                )
            except APITimeoutError as exc:
                raise LLMProviderError(f"LLM timeout: {exc}", code="timeout") from exc
            except APIConnectionError as exc:
                raise LLMProviderError(f"LLM connection error: {exc}", code="connection") from exc
            except APIStatusError as exc:
                raise LLMProviderError(
                    f"LLM API error ({exc.status_code}): {exc.message}",
                    code="api_error",
                ) from exc
            except Exception as exc:
                raise LLMProviderError(str(exc), code="unknown") from exc

            choice = response.choices[0]
            token_usage = normalize_token_usage(response.usage)
            return ChatResult(
                content=choice.message.content or "",
                token_usage=token_usage,
                model=self.model_name,
                provider=self.provider_name,
            )

        return await _call()

    async def health_check(self) -> dict[str, Any]:
        try:
            response = await self._client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "Say hello in one word."}],
                max_tokens=64,
                timeout=min(self._timeout, 15.0),
            )
            choice = response.choices[0]
            content = (choice.message.content or "").strip()
            token_usage = normalize_token_usage(response.usage)
            completion_tokens = token_usage.get("completion_tokens", 0)
            if content or completion_tokens > 0:
                return {
                    "status": "ok",
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "token_usage": token_usage,
                }
            return {
                "status": "error",
                "provider": self.provider_name,
                "model": self.model_name,
                "message": (
                    f"Empty LLM response (finish_reason={choice.finish_reason}). "
                    "Try a chat-oriented model for health probes."
                ),
            }
        except LLMProviderError as exc:
            return {"status": "error", "provider": self.provider_name, "message": str(exc)}
        except Exception as exc:
            return {"status": "error", "provider": self.provider_name, "message": str(exc)}


# Backward compatibility alias used by older imports.
BaseLLMClient = BaseLLMProvider
