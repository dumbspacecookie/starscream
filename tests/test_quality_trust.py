import time
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from starscream.api.auth import generate_api_key, hash_api_key
from starscream.api.middleware import RateLimitMiddleware
from starscream.api.schemas import FlagIn, RateIn
from starscream.api.main import app
from starscream.db.models import FlagReason

client = TestClient(app)


def test_openapi_includes_quality_trust_endpoints():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/v1/recordings/{recording_id}/rate" in paths
    assert "/v1/recordings/{recording_id}/flag" in paths
    assert "/v1/contrib/register" in paths
    assert "/v1/contributors/{contributor_id}" in paths
    assert "/v1/admin/flags" in paths


def test_rate_schema_rejects_out_of_range():
    with pytest.raises(ValidationError):
        RateIn(score=0)
    with pytest.raises(ValidationError):
        RateIn(score=6)


def test_flag_schema_accepts_reasons():
    flag = FlagIn(reason=FlagReason.MISLABELED_GPS, details="GPS is 500km off")
    assert flag.reason == FlagReason.MISLABELED_GPS


def test_api_key_generation_and_hash():
    raw, key_hash, prefix = generate_api_key()
    assert raw.startswith("ss_")
    assert len(key_hash) == 64
    assert raw.startswith(prefix)
    assert hash_api_key(raw) == key_hash


def test_peer_review_rate_requires_api_key():
    recording_id = "550e8400-e29b-41d4-a716-446655440000"
    response = client.post(
        f"/v1/recordings/{recording_id}/rate",
        json={"score": 4},
    )
    assert response.status_code == 401
    assert "API key" in response.json()["detail"]


def test_contrib_upload_requires_api_key():
    response = client.post(
        "/v1/contrib/upload",
        data={"manifest_json": "{}"},
        files={"audio": ("test.wav", b"not audio", "audio/wav")},
    )
    assert response.status_code == 401
    assert "API key" in response.json()["detail"]


def test_admin_flags_requires_admin_key():
    response = client.get("/v1/admin/flags")
    assert response.status_code in (401, 503)


def test_admin_flags_rejects_wrong_key():
    with patch("starscream.api.auth.get_settings") as mock_settings:
        mock_settings.return_value.admin_api_key = "admin-secret"
        response = client.get("/v1/admin/flags", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_rate_limit_middleware_enforces_limit():
    test_app = FastAPI()

    @test_app.get("/ping")
    async def ping():
        return {"ok": True}

    test_app.add_middleware(RateLimitMiddleware, limit_per_min=3)
    limited = TestClient(test_app)

    for _ in range(3):
        assert limited.get("/ping").status_code == 200

    blocked = limited.get("/ping")
    assert blocked.status_code == 429
    assert "Rate limit" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_rate_limit_middleware_tracks_per_ip():
    from starlette.responses import JSONResponse

    middleware = RateLimitMiddleware(FastAPI(), limit_per_min=2)

    scope_a = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": ("10.0.0.1", 1234),
    }
    scope_b = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": ("10.0.0.2", 5678),
    }

    async def call_next(request):
        return JSONResponse({"ok": True})

    middleware._windows["10.0.0.1"].extend([time.monotonic()] * 2)
    middleware._last_seen["10.0.0.1"] = time.monotonic()

    resp_a = await middleware.dispatch(Request(scope_a), call_next)
    assert resp_a.status_code == 429

    resp_b = await middleware.dispatch(Request(scope_b), call_next)
    assert resp_b.status_code == 200
