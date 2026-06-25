"""Text chunking with token counts."""

from dataclasses import dataclass

import tiktoken

ALLOWED_CHUNK_SIZES = {256, 512, 1024, 1536}
DEFAULT_CHUNK_SIZE = 512
DEFAULT_OVERLAP = 50

_ENCODING = None


def _get_encoding():
    global _ENCODING
    if _ENCODING is None:
        _ENCODING = tiktoken.get_encoding("cl100k_base")
    return _ENCODING


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    content: str
    token_count: int


def count_tokens(text: str) -> int:
    return len(_get_encoding().encode(text))


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[TextChunk]:
    if chunk_size not in ALLOWED_CHUNK_SIZES:
        raise ValueError(f"chunk_size must be one of {sorted(ALLOWED_CHUNK_SIZES)}")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    tokens = _get_encoding().encode(text.strip())
    if not tokens:
        return []

    chunks: list[TextChunk] = []
    start = 0
    chunk_index = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        piece = _get_encoding().decode(tokens[start:end]).strip()
        if piece:
            chunks.append(
                TextChunk(
                    chunk_index=chunk_index,
                    content=piece,
                    token_count=end - start,
                )
            )
            chunk_index += 1
        if end >= len(tokens):
            break
        start = end - overlap

    return chunks
