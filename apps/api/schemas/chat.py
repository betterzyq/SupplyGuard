"""Chat API schemas."""

from pydantic import BaseModel, Field

from apps.api.schemas.rag import CitationItem


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    session_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    use_memory: bool = True


class ContextBudget(BaseModel):
    max_tokens: int
    used_tokens: int


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationItem]
    memory_used: list[dict] = Field(default_factory=list)
    memory_written: list[dict] = Field(default_factory=list)
    context_budget: ContextBudget | None = None
    trace_id: str
    agent_run_id: str
    nodes_executed: list[str]
    token_usage: dict
    status: str
    route_mode: str | None = None
