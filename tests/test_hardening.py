import logging
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from starscream.api.errors import REQUEST_ID_HEADER, error_response, get_request_id, log_api_error
from starscream.api.main import app
from starscream.api.middleware import RateLimitMiddleware, RequestIdMiddleware

client = TestClient(app, raise_server_exceptions=False)

HEALTH_OK = {
    "dependencies": {
        "postgres": {"ok": True, "detail": "connected"},
        "meilisearch": {"ok": True, "detail": "available"},
        "minio": {"ok": True, "detail": "bucket reachable"},
    },
    "all_ok": True,
}


@patch("starscream.api.main.check_dependencies", return_value=HEALTH_OK)
def test_request_id_header_on_success(_mock_check):
    response = client.get("/health")
    assert response.status_code == 200
    request_id = response.headers.get(REQUEST_ID_HEADER)
    assert request_id
    assert len(request_id) >= 32


def test_request_id_echoes_client_value():
    custom_id = "client-trace-abc123"
    response = client.get("/openapi.json", headers={REQUEST_ID_HEADER: custom_id})
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == custom_id


def test_http_exception_includes_request_id_and_error_code():
    response = client.post(
        "/v1/contrib/upload",
        data={"manifest_json": "{}"},
        files={"audio": ("test.wav", b"not audio", "audio/wav")},
    )
    assert response.status_code == 401
    body = response.json()
    assert "detail" in body
    assert body["error_code"] == "auth_required"
    assert body["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_rate_limit_remaining_header():
    test_app = FastAPI()

    @test_app.get("/ping")
    async def ping():
        return {"ok": True}

    test_app.add_middleware(RateLimitMiddleware, limit_per_min=5)
    test_app.add_middleware(RequestIdMiddleware)
    limited = TestClient(test_app)

    response = limited.get("/ping")
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "5"
    assert response.headers["X-RateLimit-Remaining"] == "4"


def test_rate_limit_exceeded_includes_headers_and_error_code():
    test_app = FastAPI()

    @test_app.get("/ping")
    async def ping():
        return {"ok": True}

    test_app.add_middleware(RateLimitMiddleware, limit_per_min=2)
    test_app.add_middleware(RequestIdMiddleware)
    limited = TestClient(test_app)

    assert limited.get("/ping").status_code == 200
    assert limited.get("/ping").status_code == 200
    blocked = limited.get("/ping")

    assert blocked.status_code == 429
    assert blocked.headers["X-RateLimit-Remaining"] == "0"
    assert blocked.headers["Retry-After"] == "60"
    body = blocked.json()
    assert body["error_code"] == "rate_limit_exceeded"
    assert body["request_id"] == blocked.headers[REQUEST_ID_HEADER]
    assert "Rate limit" in body["detail"]


def test_unhandled_error_hides_details_in_production():
    test_app = FastAPI()

    @test_app.get("/boom")
    async def boom():
        raise RuntimeError("secret database password leaked")

    @test_app.exception_handler(Exception)
    async def unhandled(request, exc: Exception):
        request_id = get_request_id(request)
        log_api_error(request, status_code=500, message="Internal server error", exc=exc)
        from starscream.config import get_settings

        if get_settings().debug:
            return error_response(
                500,
                str(exc),
                error_code="internal_error",
                request_id=request_id,
            )
        return error_response(
            500,
            "Internal server error",
            error_code="internal_error",
            request_id=request_id,
        )

    test_app.add_middleware(RequestIdMiddleware)

    with patch("starscream.config.get_settings") as mock_settings:
        mock_settings.return_value.debug = False
        prod_client = TestClient(test_app, raise_server_exceptions=False)
        response = prod_client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal server error"
    assert "password" not in body["detail"]
    assert body["error_code"] == "internal_error"
    assert body["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_unhandled_error_shows_details_when_debug_enabled():
    test_app = FastAPI()

    @test_app.get("/boom")
    async def boom():
        raise RuntimeError("debug-visible failure")

    @test_app.exception_handler(Exception)
    async def unhandled(request, exc: Exception):
        request_id = get_request_id(request)
        log_api_error(request, status_code=500, message="Internal server error", exc=exc)
        from starscream.config import get_settings

        if get_settings().debug:
            return error_response(
                500,
                str(exc),
                error_code="internal_error",
                request_id=request_id,
            )
        return error_response(
            500,
            "Internal server error",
            error_code="internal_error",
            request_id=request_id,
        )

    test_app.add_middleware(RequestIdMiddleware)

    with patch("starscream.config.get_settings") as mock_settings:
        mock_settings.return_value.debug = True
        debug_client = TestClient(test_app, raise_server_exceptions=False)
        response = debug_client.get("/boom")

    assert response.status_code == 500
    assert "debug-visible failure" in response.json()["detail"]


@patch("starscream.api.main.check_dependencies", return_value=HEALTH_OK)
def test_main_unhandled_error_respects_debug_flag(_mock_check):
    from starscream.api.main import unhandled_exception_handler

    test_app = FastAPI()
    test_app.add_exception_handler(Exception, unhandled_exception_handler)
    test_app.add_middleware(RequestIdMiddleware)

    @test_app.get("/boom")
    def hardening_boom():
        raise RuntimeError("must not leak")

    with patch("starscream.api.main.get_settings") as mock_settings:
        mock_settings.return_value.debug = False
        response = TestClient(test_app, raise_server_exceptions=False).get("/boom")

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"


def test_http_exception_handler_on_main_app():
    from starscream.api.main import http_exception_handler

    test_app = FastAPI()
    test_app.add_exception_handler(HTTPException, http_exception_handler)
    test_app.add_middleware(RequestIdMiddleware)

    @test_app.get("/missing")
    def hardening_not_found():
        raise HTTPException(status_code=404, detail="Recording not found")

    response = TestClient(test_app).get("/missing")

    assert response.status_code == 404
    body = response.json()
    assert body["detail"] == "Recording not found"
    assert body["error_code"] == "not_found"
    assert body["request_id"]


def test_middleware_logs_api_errors(caplog):
    with caplog.at_level(logging.WARNING, logger="starscream.api.middleware"):
        response = client.post("/v1/contrib/upload", data={"manifest_json": "{}"})

    assert response.status_code == 401
    assert any("Contributor API key required" in record.message for record in caplog.records)
