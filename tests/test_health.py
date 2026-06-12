from unittest.mock import patch

from fastapi.testclient import TestClient

from starscream.api.main import app

client = TestClient(app)

ALL_OK = {
    "dependencies": {
        "postgres": {"ok": True, "detail": "connected"},
        "meilisearch": {"ok": True, "detail": "available"},
        "minio": {"ok": True, "detail": "bucket 'starscream-audio' reachable"},
    },
    "all_ok": True,
}

POSTGRES_DOWN = {
    "dependencies": {
        "postgres": {"ok": False, "detail": "connection refused"},
        "meilisearch": {"ok": True, "detail": "available"},
        "minio": {"ok": True, "detail": "bucket 'starscream-audio' reachable"},
    },
    "all_ok": False,
}


@patch("starscream.api.main.check_dependencies", return_value=ALL_OK)
def test_health_ok(mock_check):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["dependencies"]["postgres"]["ok"] is True
    assert body["dependencies"]["meilisearch"]["ok"] is True
    assert body["dependencies"]["minio"]["ok"] is True
    assert "version" in body
    mock_check.assert_called_once()


@patch("starscream.api.main.check_dependencies", return_value=POSTGRES_DOWN)
def test_health_degraded(mock_check):
    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["dependencies"]["postgres"]["ok"] is False
    mock_check.assert_called_once()


def test_check_dependencies_structure():
    from starscream.health import check_dependencies

    with patch("starscream.health.check_postgres", return_value={"ok": True, "detail": "connected"}):
        with patch(
            "starscream.health.check_meilisearch", return_value={"ok": True, "detail": "available"}
        ):
            with patch(
                "starscream.health.check_minio",
                return_value={"ok": True, "detail": "bucket reachable"},
            ):
                result = check_dependencies()
    assert result["all_ok"] is True
    assert set(result["dependencies"]) == {"postgres", "meilisearch", "minio"}


def test_healthcheck_cli_exits_zero_when_ok():
    from starscream.health import run_healthcheck_cli

    with patch("starscream.health.check_dependencies", return_value=ALL_OK):
        assert run_healthcheck_cli() == 0


def test_healthcheck_cli_exits_one_when_degraded():
    from starscream.health import run_healthcheck_cli

    with patch("starscream.health.check_dependencies", return_value=POSTGRES_DOWN):
        assert run_healthcheck_cli() == 1
