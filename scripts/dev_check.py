#!/usr/bin/env python3
"""One-shot development environment checker for SupplyGuard MVP-1."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check_python_version() -> tuple[bool, str]:
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 11):
        return True, f"Python {major}.{minor}"
    return False, f"Python {major}.{minor} (requires >= 3.11)"


def check_env_file() -> tuple[bool, str]:
    env_path = ROOT / ".env"
    example_path = ROOT / ".env.example"
    if env_path.exists():
        return True, ".env exists"
    if example_path.exists():
        return False, ".env missing — copy from .env.example and fill in API keys"
    return False, ".env and .env.example both missing"


async def run_checks() -> list[tuple[str, bool, str]]:
    from packages.common.cache.redis_client import check_redis_health
    from packages.common.config import get_settings
    from packages.common.db.session import check_postgres_health
    from packages.common.embedding.openai_compatible import check_embedding_health
    from packages.common.graph.neo4j_client import check_neo4j_health
    from packages.common.llm.factory import check_llm_health
    from packages.common.storage.minio_client import check_minio_health
    from packages.common.vector.qdrant_client import check_qdrant_health

    settings = get_settings()
    results: list[tuple[str, bool, str]] = []

    py_ok, py_msg = check_python_version()
    results.append(("python", py_ok, py_msg))

    env_ok, env_msg = check_env_file()
    results.append(("env_file", env_ok, env_msg))

    infra_checks = [
        ("postgres", check_postgres_health(settings)),
        ("redis", check_redis_health(settings)),
        ("qdrant", check_qdrant_health(settings)),
        ("neo4j", check_neo4j_health(settings)),
        ("minio", check_minio_health(settings)),
        ("llm", check_llm_health(settings)),
        ("embedding", check_embedding_health(settings)),
    ]

    for name, coro in infra_checks:
        try:
            outcome = await coro
            ok = outcome.get("status") == "ok"
            detail = "ok" if ok else outcome.get("message", str(outcome))
            results.append((name, ok, detail))
        except Exception as exc:
            results.append((name, False, str(exc)))

    results.append(
        (
            "fastapi_hint",
            True,
            "Run: uv run uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000",
        )
    )
    return results


def main() -> int:
    print("SupplyGuard MVP-1 dev environment check\n" + "=" * 40)
    results = asyncio.run(run_checks())

    failed = 0
    for name, ok, detail in results:
        icon = "PASS" if ok else "FAIL"
        print(f"[{icon}] {name}: {detail}")
        if not ok and name not in {"env_file"}:
            failed += 1
        elif not ok and name == "env_file":
            failed += 1

    print("=" * 40)
    if failed:
        print(f"Result: {failed} check(s) failed or degraded.")
        print("Note: llm/embedding fail if API keys are not configured in .env")
        return 1

    print("Result: all checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
