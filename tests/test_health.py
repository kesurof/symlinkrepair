from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")


def test_homepage():
    response = client.get("/")
    assert response.status_code == 200
    assert "SymlinkRepair" in response.text
