"""Base embedding client abstraction."""

from abc import ABC, abstractmethod


class BaseEmbeddingClient(ABC):
    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text."""

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts."""
