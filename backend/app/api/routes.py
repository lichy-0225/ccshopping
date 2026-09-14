from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agent.orchestrator import ShoppingAgent

router = APIRouter()
agent = ShoppingAgent()


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    channel: str = "web"
    store_id: str | None = None
    product_sku: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    action: str
    reply: str
    risk_level: str
    candidates: list[dict] = Field(default_factory=list)
    comparison: dict | None = None
    next_question: str | None = None
    used_tools: list[str] = Field(default_factory=list)
    needs_confirmation: bool = False
    truncated: bool = False
    trace_id: str


@router.get("/health", tags=["system"])
def health() -> dict[str, str]:
    mode = "deepseek" if agent.llm.configured and not agent.mock_llm else "mock"
    return {"status": "ok", "service": "shopping-agent", "mode": mode, "llm_configured": str(agent.llm.configured).lower()}


@router.get("/llm/status", tags=["system"])
def llm_status() -> dict:
    """Check configuration without revealing the API key."""
    return {"configured": agent.llm.configured, "model": agent.llm.model, "base_url": agent.llm.base_url, "mock_mode": agent.mock_llm}


@router.post("/llm/test", tags=["system"])
def llm_test() -> dict:
    """Make one small live DeepSeek call; the key is never returned."""
    return agent.llm.test_connection()


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
def chat(request: ChatRequest) -> ChatResponse:
    return ChatResponse(**agent.handle(request.session_id, request.message, request.store_id, request.product_sku))
