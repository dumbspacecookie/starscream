from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from starscream.api.middleware import RateLimitMiddleware
from starscream.config import get_settings

try:
    import fakeredis
except ImportError:
    pytest.skip("fakeredis not installed", allow_module_level=True)

@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_middleware(fake_redis, limit_per_min: int = 3) -> RateLimitMiddleware:
    with patch("redis.asyncio.from_url", return_value=fake_redis):
        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}, clear=False):
            get_settings.cache_clear()
            return RateLimitMiddleware(FastAPI(), limit_per_min=limit_per_min)


@pytest.mark.asyncio
async def test_redis_rate_limit_enforces_per_ip(fake_redis):
    middleware = _make_middleware(fake_redis, limit_per_min=2)

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

    assert (await middleware.dispatch(Request(scope_a), call_next)).status_code == 200
    assert (await middleware.dispatch(Request(scope_a), call_next)).status_code == 200
    blocked_a = await middleware.dispatch(Request(scope_a), call_next)
    assert blocked_a.status_code == 429

    resp_b = await middleware.dispatch(Request(scope_b), call_next)
    assert resp_b.status_code == 200


def test_redis_rate_limit_via_test_client(fake_redis):
    test_app = FastAPI()

    @test_app.get("/ping")
    async def ping():
        return {"ok": True}

    with patch("redis.asyncio.from_url", return_value=fake_redis):
        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:6379/0"}, clear=False):
            get_settings.cache_clear()
            test_app.add_middleware(RateLimitMiddleware, limit_per_min=3)
            client = TestClient(test_app)

            for _ in range(3):
                assert client.get("/ping").status_code == 200

            blocked = client.get("/ping")
            assert blocked.status_code == 429
            assert blocked.headers["X-RateLimit-Remaining"] == "0"
            assert blocked.json()["error_code"] == "rate_limit_exceeded"


@pytest.mark.asyncio
async def test_redis_rate_limit_sets_expiry_on_first_hit(fake_redis):
    middleware = _make_middleware(fake_redis, limit_per_min=10)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "client": ("10.0.0.9", 9999),
    }

    async def call_next(request):
        return JSONResponse({"ok": True})

    await middleware.dispatch(Request(scope), call_next)
    ttl = await fake_redis.ttl("rate_limit:10.0.0.9")
    assert 0 < ttl <= 60
