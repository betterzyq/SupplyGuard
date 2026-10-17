import asyncio
from types import SimpleNamespace
from uuid import uuid4
import pytest
from packages.benchmarks.metrics import (
    recall_at_k,
    precision_at_k,
    ndcg_at_k,
    citation_scores,
    graph_path_hit_rate,
    blocked_accuracy,
    aggregate_metrics,
)
from packages.benchmarks.enterprise_validation import validate
from packages.benchmarks.evaluators import (
    evaluate_memory_row,
    extract_entities_from_text,
    evaluate_rag_row,
)
from packages.benchmarks.dataset import EvalQuestion


def question(**kw):
    return EvalQuestion(
        id="x",
        question="q",
        user_role="enterprise",
        expected_mode="secure_rag",
        question_type="rag_qa",
        **kw,
    )


def test_strict_contracts_and_gold_are_not_live_scores():
    r = validate()
    assert r["status"] == "passed"
    assert r["evaluated_contracts"] == 17 and r["gold_only_cases"] == 8
    assert r["live_retrieval_status"] == "not_run"


@pytest.mark.parametrize("fn", [recall_at_k, precision_at_k, ndcg_at_k])
def test_no_gold_is_not_perfect_and_duplicate_credit_is_bounded(fn):
    assert fn([], [], 5) is None
    assert 0 <= fn(["a", "a", "a"], ["a"], 3) <= 1


def test_citation_exact_identity_and_different_denominators():
    assert citation_scores([{"chunk_id": "doc#11"}], ["doc#1"]) == {
        "citation_precision": 0,
        "citation_recall": 0,
    }
    assert citation_scores(
        [{"chunk_id": "a"}, {"chunk_id": "a"}, {"chunk_id": "b"}], ["a"]
    ) == {"citation_precision": 0.5, "citation_recall": 1}
    assert (
        citation_scores([{"document_id": "d", "chunk_index": 0}], ["d#0"])[
            "citation_precision"
        ]
        == 1
    )


@pytest.mark.parametrize(
    "found",
    [
        "Supplier SUP-001",
        "Supplier SUP-0011 → Material M001",
        "Material M001 → Supplier SUP-001",
        "Supplier SUP-001 → Product M001",
    ],
)
def test_full_typed_directional_path(found):
    assert graph_path_hit_rate([found], [["Supplier:SUP-001", "Material:M001"]]) == 0


def test_aggregate_na_denominators_and_empty_decisions():
    r = aggregate_metrics(
        [{"graph_path_hit_rate": 1}, {"recall_at_k": 0}, {"recall_at_k": None}]
    )
    assert r["recall_at_k"] == 0 and r["graph_path_hit_rate"] == 1
    assert r["metric_denominators"]["recall_at_k"] == 1
    assert r["blocked_accuracy"] is None
    assert (
        blocked_accuracy([{"should_be_blocked": True, "decision": "no_evidence"}]) == 0
    )


def test_no_gold_injection_or_memory_seed_credit():
    q = question(should_be_blocked=True, requires_memory=True)
    r = evaluate_rag_row(
        q,
        retrieved_ids=[],
        citations=[],
        gold_chunk_ids=[],
        top_k=5,
        permission_filter_enabled=True,
        answer="未找到足够证据。",
        should_be_blocked=True,
    )
    assert r["decision"] == "no_evidence"
    assert blocked_accuracy([r]) == 0
    assert not evaluate_memory_row(
        q, memory_used=[], answer="历史记忆 [memory:x]", session_hit=False
    )["memory_hit"]
    assert extract_entities_from_text("PO-2024-0001 SUP-001 SUP-0011") == [
        "PO-2024-0001",
        "SUP-001",
    ]


def test_benchmark_subject_lookup_is_tenant_scoped():
    from packages.benchmarks.benchmark_runner import load_user_context_for_question

    class Session:
        async def execute(self, statement):
            self.statement = statement
            return SimpleNamespace(scalar_one_or_none=lambda: None)

    s = Session()
    tenant = uuid4()
    with pytest.raises(ValueError):
        asyncio.run(load_user_context_for_question(s, question(), tenant))
    assert "users.tenant_id =" in str(s.statement)
    assert tenant in s.statement.compile().params.values()


def test_new_rag_gold_has_specific_evidence_and_two_role_policy():
    from packages.benchmarks.dataset import load_dataset

    questions = load_dataset()
    assert len(questions) == 9
    assert all(
        q.user_role == "enterprise"
        and q.policy_version == "enterprise-v2"
        and q.gold_spans
        for q in questions
    )
    assert len({q.question for q in questions}) == 9


def test_gold_resolution_requires_exact_span_and_tenant():
    from packages.benchmarks.evaluators import resolve_gold_chunk_ids

    tenant, doc_id, chunk_id = uuid4(), uuid4(), uuid4()
    doc = SimpleNamespace(id=doc_id, metadata_={"slug": "policy"})
    chunks = [
        SimpleNamespace(
            id=chunk_id, document_id=doc_id, content="Payment term Net 60 days."
        )
    ]

    class Session:
        def __init__(self):
            self.statements = []

        async def execute(self, statement):
            self.statements.append(statement)
            rows = [doc] if "FROM documents" in str(statement) else chunks
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: rows))

    s = Session()
    assert asyncio.run(
        resolve_gold_chunk_ids(
            s, tenant, ["policy"], [{"slug": "policy", "text": "Net 60 days."}]
        )
    ) == [str(chunk_id)]
    assert tenant in s.statements[0].compile().params.values()
    with pytest.raises(ValueError, match="resolution failed"):
        asyncio.run(
            resolve_gold_chunk_ids(
                s, tenant, ["policy"], [{"slug": "policy", "text": "Net 600 days."}]
            )
        )


def test_inserted_risk_event_does_not_match_shorter_graph_path():
    assert (
        graph_path_hit_rate(
            ["Supplier SUP-001 → RiskEvent EV-001 → Material M001"],
            [["Supplier:SUP-001", "Material:M001"]],
        )
        == 0
    )


def test_citation_without_identity_is_not_silently_dropped():
    result = citation_scores(
        [{"chunk_id": "a"}, {"title": "unresolvable reference"}], ["a"]
    )
    assert result == {"citation_precision": 0.5, "citation_recall": 1.0}


def test_ready_to_run_graph_annotations_match_specific_supplier():
    from pathlib import Path
    from packages.benchmarks.dataset import load_dataset

    root = Path(__file__).resolve().parents[2]
    questions = load_dataset(root / "data/eval/graph-enterprise-v2.jsonl")
    assert len(questions) == 8 and all(
        q.requires_graph and q.policy_version == "enterprise-v2" for q in questions
    )
    supplier2 = next(q for q in questions if q.id == "enterprise-graph-impact-SUP-002")
    assert all(path[0] == "Supplier:SUP-002" for path in supplier2.gold_graph_paths)
    delivery = next(q for q in questions if q.id == "enterprise-graph-delay-DE-001")
    assert delivery.gold_graph_paths == [
        ["Supplier:SUP-001", "DeliveryEvent:DE-001", "Order:PO-2024-0001"]
    ]
