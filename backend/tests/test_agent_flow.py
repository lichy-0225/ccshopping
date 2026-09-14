from fastapi.testclient import TestClient

from app.api.routes import agent
from app.main import app


client = TestClient(app)


def setup_function() -> None:
    agent.reset()
    agent.mock_llm = True
    agent.mock_llm = True


def post(session: str, message: str) -> dict:
    response = client.post("/api/v1/chat", json={"session_id": session, "message": message})
    assert response.status_code == 200
    return response.json()


def test_normal_and_multiturn_recommendation() -> None:
    first = post("case-1", "我预算200元，想买无香味洁面产品。")
    assert first["action"] == "ask"
    second = post("case-1", "更在意温和清洁。")
    assert second["action"] == "recommend"
    assert second["candidates"][0]["sku_id"] == "P101"
    assert all(item["price"] <= 200 for item in second["candidates"])


def test_budget_no_match() -> None:
    result = post("case-3", "我预算100元，想买洁面。")
    assert result["action"] == "no_match"
    assert result["candidates"] == []


def test_budget_change_recalculates() -> None:
    post("case-4", "我预算200元，想买无香洁面，更在意温和清洁。")
    result = post("case-4", "预算改成100元。")
    assert result["action"] == "no_match"
    assert result["candidates"] == []


def test_safety_response() -> None:
    result = post("case-5", "我最近脸上刺痛、泛红，想买一个刺激性强一点的产品。")
    assert result["action"] == "safe_reply"
    assert result["risk_level"] == "high"
    assert result["candidates"] == []
    assert "医疗诊断" in result["reply"]


def test_policy_unknown() -> None:
    result = post("case-6", "这款今天在线下门店有没有赠品？")
    assert result["action"] == "fallback"
    assert "无法确认" in result["reply"]


def test_exclusion_can_make_no_match() -> None:
    result = post("case-7", "预算200元，想买无香味洁面，不要香味。")
    # It asks the one missing concern first, then the explicit constraints remain active.
    assert result["action"] == "ask"
    result = post("case-7", "温和清洁。")
    assert result["action"] == "recommend"
    assert all(item["price"] <= 200 for item in result["candidates"])


def test_preference_change_recalculates() -> None:
    post("case-preference", "预算200元，想买无香洁面，更在意温和清洁。")
    result = post("case-preference", "可以有香味，改为清爽控油。")
    assert result["action"] == "recommend"
    assert result["candidates"][0]["sku_id"] == "P102"
