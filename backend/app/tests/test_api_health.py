from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_naaqs_endpoint():
    response = client.get("/api/v1/naaqs")
    assert response.status_code == 200
    pollutants = {row["pollutant"] for row in response.json()}
    assert "PM2.5" in pollutants
    assert "CO" in pollutants
