"""OpenAI-compatible embedding client."""

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from packages.common.config import Settings, get_settings
from packages.common.embedding.base import BaseEmbeddingClient


class OpenAICompatibleEmbeddingClient(BaseEmbeddingClient):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = AsyncOpenAI(
            api_key=self.settings.EMBEDDING_API_KEY,
            base_url=self.settings.EMBEDDING_BASE_URL,
            timeout=self.settings.EMBEDDING_TIMEOUT_SECONDS,
        )

    def _validate_dimension(self, vector: list[float]) -> list[float]:
        expected = self.settings.EMBEDDING_DIM
        if len(vector) != expected:
            raise ValueError(
                f"Embedding dimension mismatch: expected {expected}, got {len(vector)}"
            )
        return vector

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def embed_text(self, text: str) -> list[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(
            model=self.settings.EMBEDDING_MODEL,
            input=texts,
        )
        vectors = [item.embedding for item in response.data]
        return [self._validate_dimension(vector) for vector in vectors]


_OPENAI_COMPATIBLE_PROVIDERS = frozenset(
    {"openai_compatible", "siliconflow", "openai", "deepseek"}
)


def get_embedding_client(settings: Settings | None = None) -> BaseEmbeddingClient:
    settings = settings or get_settings()
    if settings.EMBEDDING_PROVIDER in _OPENAI_COMPATIBLE_PROVIDERS:
        return OpenAICompatibleEmbeddingClient(settings)
    raise ValueError(
        f"Unsupported embedding provider: {settings.EMBEDDING_PROVIDER}. "
        f"Supported: {sorted(_OPENAI_COMPATIBLE_PROVIDERS)}"
    )


async def check_embedding_health(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    if not settings.EMBEDDING_API_KEY or settings.EMBEDDING_API_KEY == "your_embedding_api_key":
        return {
            "status": "error",
            "message": "EMBEDDING_API_KEY is not configured",
        }
    if not settings.EMBEDDING_BASE_URL or not settings.EMBEDDING_MODEL:
        return {
            "status": "error",
            "message": "EMBEDDING_BASE_URL or EMBEDDING_MODEL is not configured",
        }
    try:
        client = AsyncOpenAI(
            api_key=settings.EMBEDDING_API_KEY,
            base_url=settings.EMBEDDING_BASE_URL,
            timeout=10.0,
        )
        response = await client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input="health check",
        )
        vector = response.data[0].embedding
        expected = settings.EMBEDDING_DIM
        if len(vector) != expected:
            return {
                "status": "error",
                "message": (
                    f"Embedding dimension mismatch: expected {expected}, got {len(vector)}. "
                    f"Set EMBEDDING_DIM={len(vector)} in .env"
                ),
            }
        return {"status": "ok", "dimension": len(vector)}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
