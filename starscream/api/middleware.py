import logging
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from starscream.api.auth import (
    API_KEY_HEADER,
    CONTRIBUTOR_STATE_KEY,
    client_ip,
    extract_api_key,
    lookup_contributor,
)
from starscream.api.errors import (
    REQUEST_ID_HEADER,
    REQUEST_ID_STATE_KEY,
    error_response,
    log_api_error,
    new_request_id,
)
from starscream.config import get_settings
from starscream.db.session import get_session_factory
from starscream.sensor.node import (
    NODE_TOKEN_HEADER,
    SENSOR_NODE_STATE_KEY,
    extract_node_token,
    lookup_sensor_node,
)

logger = logging.getLogger(__name__)

CONTRIB_POST_EXEMPT = {
    "/v1/contrib/register",
    "/v1/contrib/validate",
    "/v1/contrib/validate-batch",
}

SENSOR_POST_EXEMPT = {
    "/v1/sensor/register",
}


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign a unique request id to every request and echo it on responses."""

    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming.strip() if incoming and incoming.strip() else new_request_id()
        setattr(request.state, REQUEST_ID_STATE_KEY, request_id)

        response = await call_next(request)
        response.headers.setdefault(REQUEST_ID_HEADER, request_id)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limit per client IP (spec: 1000 req/min).

    Uses a Redis INCR+EXPIRE fixed window when ``redis_url`` is configured;
    otherwise falls back to an in-memory sliding window.
    """

    _PRUNE_INTERVAL_S = 60.0
    _IDLE_TTL_S = 120.0
    _REDIS_WINDOW_S = 60

    def __init__(self, app, limit_per_min: int | None = None):
        super().__init__(app)
        settings = get_settings()
        self.limit_per_min = limit_per_min or settings.api_rate_limit_per_min
        self._redis = None
        if settings.redis_url:
            try:
                import redis.asyncio as aioredis
            except ImportError:
                logger.warning(
                    "redis_url is set but the redis package is not installed; "
                    "using in-memory rate limiter"
                )
            else:
                self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        if self._redis is None:
            self._windows: dict[str, deque[float]] = defaultdict(deque)
            self._last_seen: dict[str, float] = {}
            self._last_prune = 0.0

    def _prune_idle(self, now: float) -> None:
        if now - self._last_prune < self._PRUNE_INTERVAL_S:
            return
        self._last_prune = now
        idle_cutoff = now - self._IDLE_TTL_S
        stale = [
            ip
            for ip, window in self._windows.items()
            if not window and self._last_seen.get(ip, 0.0) < idle_cutoff
        ]
        for ip in stale:
            self._windows.pop(ip, None)
            self._last_seen.pop(ip, None)

    def _remaining(self, window: deque[float]) -> int:
        return max(0, self.limit_per_min - len(window))

    def _rate_limit_headers(self, remaining: int) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(self.limit_per_min),
            "X-RateLimit-Remaining": str(remaining),
        }

    def _rate_limit_exceeded_response(self, request: Request) -> Response:
        request_id = getattr(request.state, REQUEST_ID_STATE_KEY, None)
        log_api_error(
            request,
            status_code=429,
            message=f"Rate limit exceeded ({self.limit_per_min} requests/min)",
        )
        headers = self._rate_limit_headers(0)
        headers["Retry-After"] = str(self._REDIS_WINDOW_S)
        return error_response(
            429,
            f"Rate limit exceeded ({self.limit_per_min} requests/min)",
            error_code="rate_limit_exceeded",
            request_id=request_id,
            headers=headers,
        )

    async def _dispatch_redis(self, request: Request, call_next, ip: str) -> Response:
        key = f"rate_limit:{ip}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, self._REDIS_WINDOW_S)

        if count > self.limit_per_min:
            return self._rate_limit_exceeded_response(request)

        remaining_after = max(0, self.limit_per_min - count)
        response = await call_next(request)
        return self._attach_headers(response, remaining_after)

    async def _dispatch_memory(self, request: Request, call_next, ip: str) -> Response:
        now = time.monotonic()
        self._last_seen[ip] = now
        self._prune_idle(now)
        window = self._windows[ip]
        cutoff = now - 60.0

        while window and window[0] < cutoff:
            window.popleft()

        if not window:
            self._windows.pop(ip, None)
            window = self._windows[ip]

        if len(window) >= self.limit_per_min:
            return self._rate_limit_exceeded_response(request)

        window.append(now)
        remaining_after = self._remaining(window)
        response = await call_next(request)
        return self._attach_headers(response, remaining_after)

    async def dispatch(self, request: Request, call_next):
        if self.limit_per_min <= 0:
            response = await call_next(request)
            return self._attach_headers(response, self.limit_per_min)

        ip = client_ip(request)
        if self._redis is not None:
            return await self._dispatch_redis(request, call_next, ip)
        return await self._dispatch_memory(request, call_next, ip)

    def _attach_headers(self, response: Response, remaining: int) -> Response:
        for key, value in self._rate_limit_headers(remaining).items():
            response.headers.setdefault(key, value)
        return response


class ContributorAuthMiddleware(BaseHTTPMiddleware):
    """Require contributor API key on POST /v1/contrib/* (except register/validate)."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        request_id = getattr(request.state, REQUEST_ID_STATE_KEY, None)

        if request.method == "POST" and path.startswith("/v1/contrib/"):
            if path not in CONTRIB_POST_EXEMPT:
                api_key = extract_api_key(request)
                if not api_key:
                    log_api_error(
                        request,
                        status_code=401,
                        message="Contributor API key required",
                    )
                    return error_response(
                        401,
                        (
                            f"Contributor API key required "
                            f"(header {API_KEY_HEADER} or Authorization: Bearer)"
                        ),
                        error_code="auth_required",
                        request_id=request_id,
                    )

                session = get_session_factory()()
                try:
                    contributor = lookup_contributor(session, api_key)
                finally:
                    session.close()

                if not contributor:
                    log_api_error(
                        request,
                        status_code=401,
                        message="Invalid or inactive contributor API key",
                    )
                    return error_response(
                        401,
                        "Invalid or inactive contributor API key",
                        error_code="invalid_api_key",
                        request_id=request_id,
                    )
                setattr(request.state, CONTRIBUTOR_STATE_KEY, contributor)

        if request.method == "POST" and path.startswith("/v1/sensor/"):
            if path not in SENSOR_POST_EXEMPT:
                api_key = extract_api_key(request)
                node_token = extract_node_token(request)
                contributor = None
                sensor_node = None

                session = get_session_factory()()
                try:
                    if api_key:
                        contributor = lookup_contributor(session, api_key)
                    if node_token:
                        sensor_node = lookup_sensor_node(session, node_token)
                finally:
                    session.close()

                if not contributor and not sensor_node:
                    log_api_error(
                        request,
                        status_code=401,
                        message="Contributor API key or node token required",
                    )
                    return error_response(
                        401,
                        (
                            f"Contributor API key ({API_KEY_HEADER}) or node token "
                            f"({NODE_TOKEN_HEADER}) required"
                        ),
                        error_code="auth_required",
                        request_id=request_id,
                    )

                if contributor:
                    setattr(request.state, CONTRIBUTOR_STATE_KEY, contributor)
                if sensor_node:
                    setattr(request.state, SENSOR_NODE_STATE_KEY, sensor_node)

        return await call_next(request)
