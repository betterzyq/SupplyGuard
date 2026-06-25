"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "SupplyGuard"
    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # LLM
    LLM_PROVIDER: str = "deepseek"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    LLM_TIMEOUT_SECONDS: float = 60.0
    LLM_MAX_RETRIES: int = 2
    LLM_FALLBACK_PROVIDER: str = ""

    # LiteLLM gateway
    LITELLM_BASE_URL: str = "http://localhost:4000"
    LITELLM_MODEL: str = "deepseek-chat"
    LITELLM_API_KEY: str = "litellm"

    # vLLM OpenAI-compatible server
    VLLM_BASE_URL: str = "http://localhost:8001/v1"
    VLLM_MODEL: str = "Qwen/Qwen2.5-7B-Instruct"
    VLLM_API_KEY: str = "EMPTY"

    # Embedding
    EMBEDDING_PROVIDER: str = "openai_compatible"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_MODEL: str = ""
    EMBEDDING_DIM: int = 1024
    EMBEDDING_TIMEOUT_SECONDS: float = 60.0
    EMBEDDING_MAX_RETRIES: int = 2

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "supplyguard"
    POSTGRES_USER: str = "supplyguard"
    POSTGRES_PASSWORD: str = "supplyguard"
    POSTGRES_URL: str = (
        "postgresql+asyncpg://supplyguard:supplyguard@localhost:5432/supplyguard"
    )

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "supplyguard_chunks"
    QDRANT_TIMEOUT_SECONDS: float = 60.0

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "supplyguard"

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "supplyguard"
    MINIO_SECRET_KEY: str = "supplyguard123"
    MINIO_BUCKET: str = "supplyguard-docs"
    MINIO_SECURE: bool = False

    # JWT (reserved for MVP-2)
    JWT_SECRET_KEY: str = "change_this_to_a_long_random_secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Observability (reserved)
    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "supplyguard-dev"

    # Model gateway (reserved)

    # Context / Memory
    MAX_CONTEXT_TOKENS: int = 8000
    SESSION_MEMORY_TTL_SECONDS: int = 86400

    @property
    def api_timeout(self) -> float:
        return self.LLM_TIMEOUT_SECONDS


@lru_cache
def get_settings() -> Settings:
    return Settings()
