"""PDF parser using pypdf."""

from pathlib import Path

from pypdf import PdfReader

from packages.rag.parsers.base import ParsedDocument


def parse_pdf(path: Path) -> ParsedDocument:
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError(f"PDF parsed empty text (no OCR): {path}")
    return ParsedDocument(text=text, mime_type="application/pdf")
