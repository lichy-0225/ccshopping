from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_mock_chat():
    response = client.post(
        "/api/v1/chat",
        json={"session_id": "test-1", "message": "想买洁面产品"},
    )
    assert response.status_code == 200
    assert response.json()["action"] == "ask"
    assert response.json()["next_question"]
