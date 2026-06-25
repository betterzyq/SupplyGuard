"""Eval dataset loading and normalization."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def normalize_supplier_code(code: str) -> str:
    upper = code.upper().strip()
    if upper.startswith("S") and not upper.startswith("SUP-"):
        digits = upper.lstrip("S")
        if digits.isdigit():
            return f"SUP-{digits.zfill(3)}"
    return upper


def normalize_entity_list(entities: list[str]) -> list[str]:
    return [normalize_supplier_code(e) if e.upper().startswith("S") and "-" not in e else e.upper() for e in entities]


@dataclass
class EvalQuestion:
    id: str
    question: str
    user_role: str
    expected_mode: str
    question_type: str
    gold_docs: list[str] = field(default_factory=list)
    gold_chunks: list[str] = field(default_factory=list)
    gold_entities: list[str] = field(default_factory=list)
    gold_graph_paths: list[list[str]] = field(default_factory=list)
    gold_answer_points: list[str] = field(default_factory=list)
    requires_permission: bool = False
    requires_memory: bool = False
    requires_graph: bool = False
    should_be_blocked: bool = False
    graph_query_type: str | None = None
    entity_code: str | None = None
    follow_up_session_id: str | None = None
    user_email: str | None = None
    session_seed: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalQuestion:
        gold_entities = normalize_entity_list(data.get("gold_entities") or [])
        entity_code = data.get("entity_code")
        if entity_code:
            entity_code = normalize_supplier_code(entity_code)
        elif gold_entities and gold_entities[0].startswith("SUP-"):
            entity_code = gold_entities[0]

        qtype = data.get("question_type") or _infer_question_type(data)

        return cls(
            id=str(data["id"]),
            question=data["question"],
            user_role=data.get("user_role", "procurement_manager"),
            expected_mode=data.get("expected_mode", "secure_rag"),
            question_type=qtype,
            gold_docs=list(data.get("gold_docs") or []),
            gold_chunks=list(data.get("gold_chunks") or []),
            gold_entities=gold_entities,
            gold_graph_paths=list(data.get("gold_graph_paths") or []),
            gold_answer_points=list(data.get("gold_answer_points") or []),
            requires_permission=bool(data.get("requires_permission", False)),
            requires_memory=bool(data.get("requires_memory", False)),
            requires_graph=bool(data.get("requires_graph", False)),
            should_be_blocked=bool(data.get("should_be_blocked", False)),
            graph_query_type=data.get("graph_query_type"),
            entity_code=entity_code,
            follow_up_session_id=data.get("follow_up_session_id"),
            user_email=data.get("user_email"),
            session_seed=list(data.get("session_seed") or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "user_role": self.user_role,
            "expected_mode": self.expected_mode,
            "question_type": self.question_type,
            "gold_docs": self.gold_docs,
            "gold_chunks": self.gold_chunks,
            "gold_entities": self.gold_entities,
            "gold_graph_paths": self.gold_graph_paths,
            "gold_answer_points": self.gold_answer_points,
            "requires_permission": self.requires_permission,
            "requires_memory": self.requires_memory,
            "requires_graph": self.requires_graph,
            "should_be_blocked": self.should_be_blocked,
            "graph_query_type": self.graph_query_type,
            "entity_code": self.entity_code,
            "follow_up_session_id": self.follow_up_session_id,
            "user_email": self.user_email,
            "session_seed": self.session_seed,
        }


def _infer_question_type(data: dict[str, Any]) -> str:
    if data.get("should_be_blocked"):
        return "permission_boundary"
    if data.get("requires_memory"):
        return "memory_followup"
    if data.get("requires_graph"):
        return "graphrag"
    if data.get("expected_mode") == "no_answer":
        return "unanswerable"
    return "rag_qa"


def default_dataset_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "eval" / "supplyguard_eval.jsonl"


def load_dataset(path: Path | None = None) -> list[EvalQuestion]:
    path = path or default_dataset_path()
    if not path.exists():
        raise FileNotFoundError(f"Eval dataset not found: {path}")
    items: list[EvalQuestion] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            items.append(EvalQuestion.from_dict(json.loads(line)))
    return items


def filter_questions(
    items: list[EvalQuestion],
    *,
    mode: str | None = None,
    question_types: list[str] | None = None,
) -> list[EvalQuestion]:
    filtered = items
    if mode == "secure_rag" or mode == "naive_rag":
        filtered = [q for q in filtered if q.expected_mode in {"secure_rag", "rag", "hybrid"} and not q.requires_graph]
    elif mode == "graphrag":
        filtered = [q for q in filtered if q.requires_graph or q.expected_mode == "graphrag"]
    elif mode == "memory":
        filtered = [q for q in filtered if q.requires_memory or q.question_type == "memory_followup"]
    elif mode == "permission":
        filtered = [q for q in filtered if q.requires_permission or q.should_be_blocked]
    if question_types:
        filtered = [q for q in filtered if q.question_type in question_types]
    return filtered
