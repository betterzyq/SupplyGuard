"""LLM provider factory and fallback wrapper."""

from __future__ import annotations

import logging
from typing import Any

from packages.common.config import Settings, get_settings
from packages.common.llm.base import BaseLLMProvider, ChatResult, LLMProviderError
from packages.common.llm.deepseek import DeepSeekProvider
from packages.common.llm.litellm import LiteLLMProvider
from packages.common.llm.vllm import VLLMProvider

logger = logging.getLogger(__name__)

_PROVIDER_CLASSES: dict[str, type[BaseLLMProvider]] = {
    "deepseek": DeepSeekProvider,
    "litellm": LiteLLMProvider,
    "vllm": VLLMProvider,
}


class FallbackLLMProvider(BaseLLMProvider):
    """Try primary provider, fall back on LLMProviderError."""

    def __init__(self, primary: BaseLLMProvider, fallback: BaseLLMProvider) -> None:
        self._primary = primary
        self._fallback = fallback
        self.provider_name = primary.provider_name
        self.model_name = primary.model_name

    async def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> ChatResult:
        try:
            result = await self._primary.chat(messages, **kwargs)
            if not result.provider:
                result.provider = self._primary.provider_name
            return result
        except LLMProviderError as exc:
            logger.warning(
                "llm_primary_failed provider=%s error=%s fallback=%s",
                self._primary.provider_name,
                exc,
                self._fallback.provider_name,
            )
            result = await self._fallback.chat(messages, **kwargs)
            result.provider = self._fallback.provider_name
            result.model = self._fallback.model_name
            token_usage = dict(result.token_usage or {})
            token_usage["fallback_from"] = self._primary.provider_name
            result.token_usage = token_usage
            return result

    async def health_check(self) -> dict[str, Any]:
        primary = await self._primary.health_check()
        if primary.get("status") == "ok":
            primary["fallback"] = self._fallback.provider_name
            return primary
        fallback = await self._fallback.health_check()
        if fallback.get("status") == "ok":
            fallback["used_fallback"] = True
            fallback["primary_error"] = primary.get("message")
        return fallback

    def get_model_info(self):
        return self._primary.get_model_info()

    def estimate_cost(self, token_usage: dict[str, Any] | None) -> float:
        model = (token_usage or {}).get("model") or self.model_name
        return self._primary.estimate_cost({**(token_usage or {}), "model": model})


def _resolve_fallback_provider(settings: Settings) -> str | None:
    explicit = (settings.LLM_FALLBACK_PROVIDER or "").strip()
    if explicit:
        return explicit
    if settings.LLM_PROVIDER in {"litellm", "vllm"}:
        return "deepseek"
    return None


def create_provider(
    settings: Settings | None = None,
    *,
    provider_name: str | None = None,
) -> BaseLLMProvider:
    settings = settings or get_settings()
    name = (provider_name or settings.LLM_PROVIDER or "deepseek").strip().lower()
    provider_cls = _PROVIDER_CLASSES.get(name)
    if provider_cls is None:
        raise LLMProviderError(
            f"Unsupported LLM provider: {name}. Supported: {', '.join(_PROVIDER_CLASSES)}",
            code="unsupported_provider",
        )
    return provider_cls(settings)


def get_llm_client(settings: Settings | None = None) -> BaseLLMProvider:
    settings = settings or get_settings()
    primary = create_provider(settings)
    fallback_name = _resolve_fallback_provider(settings)
    if fallback_name and fallback_name != settings.LLM_PROVIDER:
        try:
            fallback = create_provider(settings, provider_name=fallback_name)
            return FallbackLLMProvider(primary, fallback)
        except LLMProviderError as exc:
            logger.warning("llm_fallback_unavailable name=%s error=%s", fallback_name, exc)
    return primary


async def check_llm_health(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    try:
        provider = get_llm_client(settings)
        result = await provider.health_check()
        info = provider.get_model_info()
        result.setdefault("provider", info.provider)
        result.setdefault("model", info.model)
        return result
    except LLMProviderError as exc:
        return {
            "status": "error",
            "provider": settings.LLM_PROVIDER,
            "message": str(exc),
            "code": exc.code,
        }
