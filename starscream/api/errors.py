"""Consistent API error responses and request-id helpers."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from starlette.requests import Request
from starlette.responses import JSONResponse

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_STATE_KEY = "request_id"

logger = logging.getLogger(__name__)


def new_request_id() -> str:
    return str(uuid4())


def get_request_id(request: Request) -> str | None:
    return getattr(request.state, REQUEST_ID_STATE_KEY, None)


def error_body(
    message: str | dict[str, Any] | list[Any],
    *,
    error_code: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"detail": message}
    if error_code is not None:
        body["error_code"] = error_code
    if request_id is not None:
        body["request_id"] = request_id
    return body


def error_response(
    status_code: int,
    message: str | dict[str, Any] | list[Any],
    *,
    error_code: str | None = None,
    request_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response_headers = dict(headers or {})
    if request_id is not None:
        response_headers.setdefault(REQUEST_ID_HEADER, request_id)
    return JSONResponse(
        status_code=status_code,
        content=error_body(message, error_code=error_code, request_id=request_id),
        headers=response_headers,
    )


def log_api_error(
    request: Request,
    *,
    status_code: int,
    message: str,
    exc: BaseException | None = None,
) -> None:
    request_id = get_request_id(request)
    extra = {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
    }
    if exc is not None:
        logger.exception("API error: %s", message, extra=extra)
    else:
        logger.warning("API error: %s", message, extra=extra)
