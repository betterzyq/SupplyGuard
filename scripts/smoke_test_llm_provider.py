#!/usr/bin/env python3
"""LLM provider smoke test."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
PASSWORD = "password123"


def record(name: str, passed: bool, detail: str = "") -> bool:
    status = "PASS" if passed else "FAIL"
    suffix = f" ({detail})" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return passed


async def login(client: httpx.AsyncClient) -> str:
    response = await client.post(
        f"{API_BASE}/api/v1/auth/login",
        json={"email": "procurement_manager@example.com", "password": PASSWORD},
    )
    response.raise_for_status()
    return response.json()["access_token"]


async def main() -> int:
    passed = 0
    total = 0

    from packages.common.config import Settings
    from packages.common.llm.base import LLMProviderError
    from packages.common.llm.deepseek import DeepSeekProvider
    from packages.common.llm.factory import (
        FallbackLLMProvider,
        _resolve_fallback_provider,
        check_llm_health,
        create_provider,
        get_llm_client,
    )
    from packages.common.llm.litellm import LiteLLMProvider
    from packages.common.llm.vllm import VLLMProvider

    settings = Settings()

    total += 1
    health = await check_llm_health(settings)
    if record("DeepSeekProvider health check", health.get("status") == "ok", health.get("model", "")):
        passed += 1

    total += 1
    provider = create_provider(settings, provider_name="deepseek")
    info_ok = provider.provider_name == "deepseek" and bool(provider.model_name)
    if record("Provider factory creates deepseek", info_ok, provider.model_name):
        passed += 1

    total += 1
    chat_result = await provider.chat([{"role": "user", "content": "Reply with the word OK only."}])
    usage_ok = bool(chat_result.content) and chat_result.token_usage.get("total_tokens", 0) > 0
    if record(
        "token usage returned from chat",
        usage_ok,
        str(chat_result.token_usage),
    ):
        passed += 1

    total += 1
    fallback_provider = get_llm_client(settings)
    fallback_ok = fallback_provider is not None
    if record("get_llm_client returns provider", fallback_ok, type(fallback_provider).__name__):
        passed += 1

    async with httpx.AsyncClient(base_url=API_BASE, timeout=120.0) as client:
        token = await login(client)
        chat_resp = await client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "Public Supply Policy 的主要内容是什么？", "top_k": 3, "use_memory": False},
        )
        total += 1
        chat_ok = chat_resp.status_code == 200 and bool(chat_resp.json().get("answer"))
        if record("/chat still works with provider abstraction", chat_ok, str(chat_resp.status_code)):
            passed += 1

        deps_resp = await client.get("/health/dependencies")
        total += 1
        llm_dep = deps_resp.json().get("dependencies", {}).get("llm", {})
        if record(
            "health dependencies includes llm",
            deps_resp.status_code == 200 and llm_dep.get("status") == "ok",
            llm_dep.get("status", ""),
        ):
            passed += 1

    total += 1
    litellm_error = ""
    try:
        LiteLLMProvider(Settings(LITELLM_BASE_URL=""))
    except LLMProviderError as exc:
        litellm_error = exc.code
    if record(
        "litellm unconfigured returns clear error",
        litellm_error == "not_configured",
        litellm_error,
    ):
        passed += 1

    total += 1
    vllm_error = ""
    try:
        VLLMProvider(Settings(VLLM_BASE_URL=""))
    except LLMProviderError as exc:
        vllm_error = exc.code
    if record(
        "vllm unconfigured returns clear error",
        vllm_error == "not_configured",
        vllm_error,
    ):
        passed += 1

    total += 1
    cost = provider.estimate_cost({"prompt_tokens": 1000, "completion_tokens": 200})
    if record("estimate_cost works", cost >= 0, f"${cost}"):
        passed += 1

    total += 1
    fallback_name = _resolve_fallback_provider(Settings(LLM_PROVIDER="litellm"))
    if record("fallback resolves to deepseek for litellm", fallback_name == "deepseek", fallback_name or "none"):
        passed += 1

    total += 1
    client_provider = get_llm_client(settings)
    is_fallback_wrapper = isinstance(client_provider, FallbackLLMProvider)
    if record(
        "fallback wrapper available for litellm/vllm",
        settings.LLM_PROVIDER == "deepseek" or is_fallback_wrapper,
        type(client_provider).__name__,
    ):
        passed += 1

    print(f"\nResult: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
