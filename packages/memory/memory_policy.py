"""Memory write/read policy and sanitization."""

from __future__ import annotations

import re
from typing import Any

from packages.authz.rbac import UserContext
from packages.memory.memory_types import (
    BUSINESS_MEMORY_TYPES,
    BusinessMemoryType,
    MemoryRecord,
    MemoryScope,
    MemoryWriteEvent,
    UserMemoryType,
)

SENSITIVE_PATTERNS = (
    re.compile(r"sk-[a-zA-Z0-9]{10,}", re.IGNORECASE),
    re.compile(r"\bapi[_-]?key\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\bbearer\s+[a-zA-Z0-9._\-]+", re.IGNORECASE),
    re.compile(r"\bpassword\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\btoken\s*[:=]\s*\S+", re.IGNORECASE),
)

CONTRACT_BLOCK_PATTERN = re.compile(
    r"(payment terms|net \d+|付款条款|合同金额|unit price|违约)",
    re.IGNORECASE,
)

PREFERENCE_KEYWORDS = ("偏好", "喜欢", "习惯", "prefer", "以后请", "报告格式")
FOCUS_SUPPLIER_KEYWORDS = ("关注", "重点分析", "常看")
RISK_HISTORY_KEYWORDS = ("风险等级", "调高", "调低", "risk score", "风险升高", "风险高")
FOLLOWUP_KEYWORDS = ("上次", "之前", "上一轮", "那个供应商", "历史分析")


def detect_sensitive_content(content: str) -> list[str]:
    reasons: list[str] = []
    for pattern in SENSITIVE_PATTERNS:
        if pattern.search(content):
            reasons.append(f"matched pattern: {pattern.pattern}")
    if len(content) > 800 and CONTRACT_BLOCK_PATTERN.search(content):
        reasons.append("long contract-like content block")
    return reasons


def sanitize_memory_content(content: str, *, max_length: int = 500) -> str:
    cleaned = content.strip()
    for pattern in SENSITIVE_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    if len(cleaned) > max_length:
        cleaned = cleaned[: max_length - 3] + "..."
    return cleaned


def classify_memory_type(content: str, context: dict[str, Any] | None = None) -> str:
    context = context or {}
    lowered = content.lower()
    if context.get("is_analysis_conclusion") or any(k in content for k in RISK_HISTORY_KEYWORDS):
        return BusinessMemoryType.SUPPLIER_RISK_HISTORY
    if context.get("is_recommendation_feedback"):
        return BusinessMemoryType.RECOMMENDATION_FEEDBACK
    if any(k in content for k in PREFERENCE_KEYWORDS):
        return UserMemoryType.PREFERENCE
    if any(k in content for k in FOCUS_SUPPLIER_KEYWORDS):
        return UserMemoryType.FOCUS_SUPPLIER
    if context.get("scope") == MemoryScope.BUSINESS:
        return BusinessMemoryType.BUSINESS_DECISION
    return UserMemoryType.FEEDBACK


def build_memory_scope(user_context: UserContext, content: str) -> dict[str, Any]:
    scope: dict[str, Any] = {
        "tenant_id": str(user_context.tenant_id),
        "user_id": str(user_context.user_id),
    }
    if user_context.is_external_supplier and user_context.supplier_id:
        scope["supplier_id"] = str(user_context.supplier_id)
    match = re.search(r"\b(SUP-\d{3})\b", content, re.IGNORECASE)
    if match:
        scope["entity_supplier_code"] = match.group(1).upper()
    return scope


def should_write_memory(event: MemoryWriteEvent) -> tuple[bool, str]:
    if not event.content or len(event.content.strip()) < 8:
        return False, "content too short"

    sensitive = detect_sensitive_content(event.content)
    if sensitive:
        return False, f"sensitive content detected: {sensitive[0]}"

    if event.is_user_explicit or event.is_analysis_conclusion:
        return True, "explicit or analysis conclusion"

    memory_type = event.memory_type or classify_memory_type(
        event.content,
        {
            "is_analysis_conclusion": event.is_analysis_conclusion,
            "scope": event.scope,
        },
    )
    if memory_type in BUSINESS_MEMORY_TYPES and event.is_analysis_conclusion:
        return True, "business analysis memory"

    if memory_type in {UserMemoryType.PREFERENCE, UserMemoryType.FOCUS_SUPPLIER}:
        return True, "user preference memory"

    if len(event.content) > 600:
        return False, "content too long for incidental memory"

    return False, "one-off query not worth persisting"


def can_read_memory(user_context: UserContext, memory: MemoryRecord) -> bool:
    if memory.tenant_id != user_context.tenant_id:
        return False

    if user_context.is_admin:
        return True

    memory_scope = memory.metadata_.get("scope", memory.scope)

    if memory_scope == MemoryScope.BUSINESS:
        if memory.supplier_id and user_context.is_external_supplier:
            return user_context.supplier_id == memory.supplier_id
        if memory.user_id != user_context.user_id:
            if memory.memory_type not in BUSINESS_MEMORY_TYPES:
                return False
        return True

    if memory.user_id != user_context.user_id:
        return False

    if user_context.is_external_supplier and memory.supplier_id:
        return user_context.supplier_id == memory.supplier_id

    return True


def is_memory_followup_query(query: str) -> bool:
    return any(keyword in query for keyword in FOLLOWUP_KEYWORDS)
