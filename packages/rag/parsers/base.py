"""Parser base types."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    mime_type: str
