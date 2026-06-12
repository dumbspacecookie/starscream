from unittest.mock import patch

from fastapi.testclient import TestClient

from starscream.api.main import app

client = TestClient(app)

HEALTH_OK = {
    "dependencies": {
        "postgres": {"ok": True, "detail": "connected"},
        "meilisearch": {"ok": True, "detail": "available"},
        "minio": {"ok": True, "detail": "bucket reachable"},
    },
    "all_ok": True,
}


@patch("starscream.api.main.check_dependencies", return_value=HEALTH_OK)
def test_health(_mock_check):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_docs():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "Starscream" in response.json()["info"]["title"]
