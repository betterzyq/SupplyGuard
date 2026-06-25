"""DeepSeek LLM provider."""

from __future__ import annotations

from packages.common.config import Settings, get_settings
from packages.common.llm.base import BaseLLMProvider, LLMProviderError, OpenAICompatibleProvider

_PLACEHOLDER_KEYS = frozenset({"", "your-deepseek-api-key", "your_deepseek_api_key"})


class DeepSeekProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        api_key = settings.DEEPSEEK_API_KEY
        if api_key in _PLACEHOLDER_KEYS:
            raise LLMProviderError(
                "DEEPSEEK_API_KEY is not configured",
                code="not_configured",
            )
        super().__init__(
            provider_name="deepseek",
            model=settings.DEEPSEEK_MODEL,
            api_key=api_key,
            base_url=settings.DEEPSEEK_BASE_URL,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )


# Backward compatibility aliases.
DeepSeekLLMClient = DeepSeekProvider


def get_llm_client(settings: Settings | None = None) -> BaseLLMProvider:
    from packages.common.llm.factory import get_llm_client as _get

    return _get(settings)


async def check_llm_health(settings: Settings | None = None) -> dict:
    from packages.common.llm.factory import check_llm_health as _check

    return await _check(settings)
