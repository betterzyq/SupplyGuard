"""Rule-based review node."""

from __future__ import annotations

from packages.agents.answer_reviewer import review_answer
from packages.agents.state import AgentState
from packages.rag.prompts import NO_EVIDENCE_ANSWER, NO_PERMISSION_ANSWER


async def review_node(state: AgentState) -> AgentState:
    unified = state.get("unified_evidence") or []
    user_context = state["user_context"]
    passed, errors = review_answer(
        answer=state.get("draft_answer") or "",
        evidence=unified,
        user_context=user_context,
        status=state.get("status"),
    )

    answer = state.get("draft_answer") or NO_EVIDENCE_ANSWER
    if not passed:
        if not unified:
            answer = NO_EVIDENCE_ANSWER
        else:
            answer = f"{answer}\n\n[review_warning] {'; '.join(errors)}"

    status = state.get("status") or ("answered" if unified else "no_evidence")
    if state.get("status") == "blocked":
        status = "blocked"

    return {
        "final_answer": answer,
        "review_passed": passed,
        "errors": errors,
        "status": status,
        "nodes_executed": ["review"],
    }
