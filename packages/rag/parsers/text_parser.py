"""Plain text and markdown parser."""

from pathlib import Path

from packages.rag.parsers.base import ParsedDocument


def parse_text(path: Path, *, mime_type: str = "text/plain") -> ParsedDocument:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Empty text file: {path}")
    return ParsedDocument(text=text, mime_type=mime_type)
