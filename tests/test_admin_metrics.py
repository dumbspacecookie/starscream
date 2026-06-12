from unittest.mock import patch

from fastapi.testclient import TestClient

from starscream.api.main import app
from starscream.pipeline.metrics import PipelineMetrics

client = TestClient(app)


def test_admin_metrics_endpoint_in_openapi():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/v1/admin/metrics" in response.json()["paths"]


def test_admin_metrics_requires_admin_key():
    response = client.get("/v1/admin/metrics")
    assert response.status_code in (401, 503)


def test_admin_metrics_returns_pipeline_counters():
    metrics = PipelineMetrics(
        enrichment_geocode_failures=2,
        enrichment_habitat_failures=1,
        enrichment_weather_failures=0,
        enrichment_osm_failures=3,
        index_failures=4,
        fingerprint_fallbacks=5,
    )

    with (
        patch("starscream.api.auth.get_settings") as mock_settings,
        patch("starscream.api.routes.admin.get_metrics", return_value=metrics),
    ):
        mock_settings.return_value.admin_api_key = "admin-secret"
        response = client.get("/v1/admin/metrics", headers={"X-API-Key": "admin-secret"})

    assert response.status_code == 200
    assert response.json() == {
        "enrichment_geocode_failures": 2,
        "enrichment_habitat_failures": 1,
        "enrichment_weather_failures": 0,
        "enrichment_osm_failures": 3,
        "index_failures": 4,
        "fingerprint_fallbacks": 5,
    }
