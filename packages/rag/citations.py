"""Citation helpers."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

CITATION_PATTERN = re.compile(
    r"\[doc:([0-9a-fA-F-]{36})#chunk:(\d+)\]"
)


@dataclass(frozen=True)
class Citation:
    document_id: uuid.UUID
    chunk_id: uuid.UUID | None
    chunk_index: int
    title: str
    score: float
    snippet: str

    def to_dict(self) -> dict:
        return {
            "document_id": str(self.document_id),
            "chunk_id": str(self.chunk_id) if self.chunk_id else None,
            "chunk_index": self.chunk_index,
            "title": self.title,
            "score": self.score,
            "snippet": self.snippet,
        }


def format_citation_marker(document_id: uuid.UUID, chunk_index: int) -> str:
    return f"[doc:{document_id}#chunk:{chunk_index}]"


def extract_citation_markers(answer: str) -> list[tuple[uuid.UUID, int]]:
    markers: list[tuple[uuid.UUID, int]] = []
    for match in CITATION_PATTERN.finditer(answer):
        markers.append((uuid.UUID(match.group(1)), int(match.group(2))))
    return markers


def build_evidence_block(chunks: list[dict]) -> str:
    lines: list[str] = []
    for item in chunks:
        marker = format_citation_marker(item["document_id"], item["chunk_index"])
        lines.append(f"{marker}\n{item['content']}")
    return "\n\n".join(lines)
