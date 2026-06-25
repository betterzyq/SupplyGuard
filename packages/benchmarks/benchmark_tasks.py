"""Background benchmark execution for long-running API jobs."""

from __future__ import annotations

import asyncio
import logging
import uuid

from packages.authz.rbac import UserContext
from packages.benchmarks.benchmark_repo import finalize_benchmark_run, get_benchmark_run
from packages.benchmarks.benchmark_runner import BenchmarkConfig, run_benchmark
from packages.common.db.session import get_session_factory
from packages.observability.trace_context import set_trace_id

logger = logging.getLogger(__name__)


def schedule_benchmark_run(
    *,
    run_id: uuid.UUID,
    admin_context: UserContext,
    config: BenchmarkConfig,
    trace_id: str,
) -> None:
    asyncio.create_task(_execute_benchmark_run(run_id, admin_context, config, trace_id))


async def _execute_benchmark_run(
    run_id: uuid.UUID,
    admin_context: UserContext,
    config: BenchmarkConfig,
    trace_id: str,
) -> None:
    set_trace_id(trace_id)
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            target_run = await get_benchmark_run(session, run_id)
            if target_run is None:
                logger.error("benchmark background run not found run_id=%s", run_id)
                return
            await run_benchmark(
                session,
                admin_context=admin_context,
                config=config,
                target_run=target_run,
            )
            await session.commit()
            logger.info("benchmark background completed run_id=%s mode=%s", run_id, config.mode)
        except Exception as exc:
            await session.rollback()
            logger.exception("benchmark background failed run_id=%s", run_id)
            async with session_factory() as err_session:
                run = await get_benchmark_run(err_session, run_id)
                if run is not None and run.status == "running":
                    await finalize_benchmark_run(
                        err_session,
                        run,
                        status="failed",
                        summary={},
                        error_message=str(exc) or exc.__class__.__name__,
                    )
                    await err_session.commit()
