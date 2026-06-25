"""Compress evidence text for prompt budget."""

from __future__ import annotations


def compress_evidence_content(content: str, *, max_chars: int = 600) -> str:
    text = content.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."
