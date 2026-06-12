import time

from fastapi import FastAPI
from starlette.responses import JSONResponse

from starscream.api.middleware import RateLimitMiddleware


async def _ok(request):
    return JSONResponse({"ok": True})


def test_rate_limit_prunes_idle_ips():
    middleware = RateLimitMiddleware(FastAPI(), limit_per_min=10)
    now = time.monotonic()
    middleware._windows["idle-ip"] = middleware._windows["idle-ip"]
    middleware._last_seen["idle-ip"] = now - 300
    middleware._last_prune = 0.0

    middleware._prune_idle(now)

    assert "idle-ip" not in middleware._windows
    assert "idle-ip" not in middleware._last_seen
