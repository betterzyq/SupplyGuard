"""LiteLLM gateway provider (OpenAI-compatible proxy)."""

from __future__ import annotations

from packages.common.config import Settings, get_settings
from packages.common.llm.base import LLMProviderError, OpenAICompatibleProvider


class LiteLLMProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        base_url = (settings.LITELLM_BASE_URL or "").strip()
        if not base_url:
            raise LLMProviderError(
                "LITELLM_BASE_URL is not configured",
                code="not_configured",
            )
        if not base_url.endswith("/v1"):
            base_url = f"{base_url.rstrip('/')}/v1"
        super().__init__(
            provider_name="litellm",
            model=settings.LITELLM_MODEL,
            api_key=settings.LITELLM_API_KEY or "litellm",
            base_url=base_url,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )
