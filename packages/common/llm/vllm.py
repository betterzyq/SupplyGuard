"""vLLM OpenAI-compatible server provider."""

from __future__ import annotations

from packages.common.config import Settings, get_settings
from packages.common.llm.base import LLMProviderError, OpenAICompatibleProvider


class VLLMProvider(OpenAICompatibleProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        base_url = (settings.VLLM_BASE_URL or "").strip()
        if not base_url:
            raise LLMProviderError(
                "VLLM_BASE_URL is not configured",
                code="not_configured",
            )
        super().__init__(
            provider_name="vllm",
            model=settings.VLLM_MODEL,
            api_key=settings.VLLM_API_KEY or "EMPTY",
            base_url=base_url,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )
