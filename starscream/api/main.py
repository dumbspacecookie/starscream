import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from starscream import __version__
from starscream.config import get_settings
from starscream.health import check_dependencies
from starscream.api.errors import error_response, get_request_id, log_api_error
from starscream.api.graphql import graphql_api_router, graphql_ide_router
from starscream.api.middleware import (
    ContributorAuthMiddleware,
    RateLimitMiddleware,
    RequestIdMiddleware,
)
from starscream.api.routes import api_router
from starscream.jobs.redis_dispatch import get_redis_consumer
from starscream.jobs.worker import get_worker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_redis_consumer().start()
    yield
    get_redis_consumer().stop()
    get_worker().shutdown()

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"

app = FastAPI(
    title="Starscream",
    description="The open catalog of all sound on Earth",
    version=__version__,
    lifespan=lifespan,
)

def _cors_origins() -> list[str]:
    raw = get_settings().cors_origins.strip()
    if not raw or raw == "*":
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(ContributorAuthMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)


def _http_error_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limit_exceeded",
        502: "bad_gateway",
        503: "service_unavailable",
    }.get(status_code, "http_error")


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = get_request_id(request)
    detail = exc.detail if isinstance(exc.detail, (str, dict, list)) else str(exc.detail)
    log_api_error(request, status_code=exc.status_code, message=str(detail))
    return error_response(
        exc.status_code,
        detail,
        error_code=_http_error_code(exc.status_code),
        request_id=request_id,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = get_request_id(request)
    detail = exc.detail if isinstance(exc.detail, (str, dict, list)) else str(exc.detail)
    log_api_error(request, status_code=exc.status_code, message=str(detail))
    return error_response(
        exc.status_code,
        detail,
        error_code=_http_error_code(exc.status_code),
        request_id=request_id,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = get_request_id(request)
    log_api_error(request, status_code=422, message="Request validation failed")
    return error_response(
        422,
        exc.errors(),
        error_code="validation_error",
        request_id=request_id,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = get_request_id(request)
    log_api_error(
        request,
        status_code=500,
        message="Internal server error",
        exc=exc,
    )
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

app.include_router(api_router)
app.include_router(graphql_api_router, prefix="/v1/graphql")
app.include_router(graphql_ide_router, prefix="/graphql")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def root():
    return RedirectResponse("/explore")


@app.get("/upload")
def upload_page():
    page = STATIC_DIR / "upload.html"
    if not page.exists():
        return {"error": "upload UI not found"}
    return FileResponse(page)


@app.get("/explore")
def explore_page():
    page = STATIC_DIR / "explore.html"
    if not page.exists():
        return {"error": "explore UI not found"}
    return FileResponse(page)


@app.get("/recording")
def recording_page():
    page = STATIC_DIR / "recording.html"
    if not page.exists():
        return {"error": "recording UI not found"}
    return FileResponse(page)


@app.get("/stats")
def stats_page():
    page = STATIC_DIR / "stats.html"
    if not page.exists():
        return {"error": "stats UI not found"}
    return FileResponse(page)


@app.get("/contributors-page")
def contributors_page():
    page = STATIC_DIR / "contributors.html"
    if not page.exists():
        return {"error": "contributors UI not found"}
    return FileResponse(page)


@app.get("/leaderboard")
def leaderboard_page():
    page = STATIC_DIR / "leaderboard.html"
    if not page.exists():
        return {"error": "leaderboard UI not found"}
    return FileResponse(page)


@app.get("/batch")
def batch_page():
    page = STATIC_DIR / "batch.html"
    if not page.exists():
        return {"error": "batch UI not found"}
    return FileResponse(page)


@app.get("/mobile")
def mobile_page():
    page = STATIC_DIR / "mobile.html"
    if not page.exists():
        return {"error": "mobile UI not found"}
    return FileResponse(page)


@app.get("/stream")
def stream_page():
    page = STATIC_DIR / "stream.html"
    if not page.exists():
        return {"error": "stream UI not found"}
    return FileResponse(page)


@app.get("/manifest.webmanifest")
def webmanifest():
    manifest = STATIC_DIR / "manifest.webmanifest"
    if not manifest.exists():
        return {"error": "manifest not found"}
    return FileResponse(manifest, media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    sw = STATIC_DIR / "sw.js"
    if not sw.exists():
        return {"error": "service worker not found"}
    return FileResponse(
        sw,
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


@app.get("/docs/{doc_path:path}")
def serve_doc(doc_path: str):
    doc_file = DOCS_DIR / doc_path
    if doc_file.exists() and doc_file.is_file():
        return FileResponse(doc_file)
    return {"error": "doc not found"}


@app.get("/health")
def health():
    probe = check_dependencies()
    body = {
        "status": "ok" if probe["all_ok"] else "degraded",
        "version": __version__,
        "dependencies": probe["dependencies"],
    }
    status_code = 200 if probe["all_ok"] else 503
    return JSONResponse(content=body, status_code=status_code)
