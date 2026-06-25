"""Permission boundary benchmark — reuses RAG retrieval checks."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.rbac import UserContext
from packages.benchmarks.dataset import EvalQuestion
from packages.benchmarks.rag_benchmark import run_rag_benchmark_item


async def run_permission_benchmark_item(
    session: AsyncSession,
    user_context: UserContext,
    question: EvalQuestion,
    *,
    top_k: int = 5,
    chunk_size: int = 512,
) -> dict:
    """Always run with permission filter enabled."""
    return await run_rag_benchmark_item(
        session,
        user_context,
        question,
        mode="secure_rag",
        top_k=top_k,
        chunk_size=chunk_size,
        permission_filter=True,
    )
