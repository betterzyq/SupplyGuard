"""GraphRAG benchmark execution."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.rbac import UserContext
from packages.benchmarks.dataset import EvalQuestion
from packages.benchmarks.evaluators import evaluate_graph_row, extract_entities_from_text
from packages.graphrag.graph_retriever import execute_graph_query


async def run_graphrag_benchmark_item(
    session: AsyncSession,
    user_context: UserContext,
    question: EvalQuestion,
    *,
    top_k: int = 20,
) -> dict[str, Any]:
    query_type = question.graph_query_type or "supplier_impact"
    try:
        result = await execute_graph_query(
            user_context,
            query=question.question,
            query_type=query_type,
            entity_code=question.entity_code,
            top_k=top_k,
            trace_id=str(uuid.uuid4()),
            session=session,
        )
        path_texts = [path.path_text for path in result.graph_paths]
        graph_paths = [path.to_dict() for path in result.graph_paths]
        found_entities = extract_entities_from_text(" ".join(path_texts))
        found_entities.extend(result.affected_suppliers)
        found_entities.extend(result.affected_materials)
        found_entities.extend(result.affected_products)
        found_entities.extend(result.affected_orders)
        found_entities.extend(result.affected_customers)
        found_entities = sorted(set(found_entities))

        graph_metrics = evaluate_graph_row(question, path_texts=path_texts, found_entities=found_entities)
        blocked = result.permission_decision == "denied" or result.result_count == 0
        graph_metrics["failure"] = bool(result.error_message) and not blocked
        graph_metrics["was_blocked_or_no_evidence"] = blocked and question.should_be_blocked
        graph_metrics["should_be_blocked"] = question.should_be_blocked
        graph_metrics["requires_permission"] = question.requires_permission

        return {
            "predicted_answer": path_texts[0] if path_texts else (result.error_message or "no graph paths"),
            "metrics": graph_metrics,
            "latency_ms": result.latency_ms,
            "token_usage": {},
            "token_usage_total": 0,
            "retrieved_ids": [],
            "citations": [],
            "graph_paths": graph_paths,
            "memory_used": [],
            "error": result.error_message,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "predicted_answer": None,
            "metrics": {
                "graph_path_hit_rate": 0.0,
                "entity_recall": 0.0,
                "affected_entity_accuracy": 0.0,
                "failure": True,
            },
            "latency_ms": 0,
            "token_usage": {},
            "token_usage_total": 0,
            "retrieved_ids": [],
            "citations": [],
            "graph_paths": [],
            "memory_used": [],
            "error": str(exc),
        }
