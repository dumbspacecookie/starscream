"""Dependency health checks shared by the API and deployment scripts."""

from __future__ import annotations

import logging
from typing import Any

import boto3
import httpx
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from starscream.config import Settings, get_settings

logger = logging.getLogger(__name__)


def check_postgres(database_url: str) -> dict[str, Any]:
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "detail": "connected"}
    except SQLAlchemyError as exc:
        logger.debug("Postgres health check failed: %s", exc)
        return {"ok": False, "detail": str(exc)}


def check_meilisearch(url: str, api_key: str = "") -> dict[str, Any]:
    health_url = f"{url.rstrip('/')}/health"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        response = httpx.get(health_url, headers=headers, timeout=5.0)
        if response.status_code == 200:
            return {"ok": True, "detail": "available"}
        return {"ok": False, "detail": f"HTTP {response.status_code}"}
    except httpx.HTTPError as exc:
        logger.debug("Meilisearch health check failed: %s", exc)
        return {"ok": False, "detail": str(exc)}


def check_minio(
    endpoint: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    region: str = "us-east-1",
) -> dict[str, Any]:
    try:
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        client.head_bucket(Bucket=bucket)
        return {"ok": True, "detail": f"bucket {bucket!r} reachable"}
    except ClientError as exc:
        logger.debug("MinIO health check failed: %s", exc)
        code = exc.response.get("Error", {}).get("Code", "unknown")
        # Bucket missing is OK before seed; service is up.
        if code in ("404", "NoSuchBucket", "Not Found"):
            return {"ok": True, "detail": f"service up (bucket {bucket!r} not created yet)"}
        return {"ok": False, "detail": f"{code}: {exc}"}
    except Exception as exc:
        logger.debug("MinIO health check failed: %s", exc)
        return {"ok": False, "detail": str(exc)}


def check_dependencies(settings: Settings | None = None) -> dict[str, Any]:
    """Return dependency statuses and whether all checks passed."""
    cfg = settings or get_settings()
    dependencies = {
        "postgres": check_postgres(cfg.database_url),
        "meilisearch": check_meilisearch(cfg.meilisearch_url, cfg.meilisearch_api_key),
        "minio": check_minio(
            cfg.s3_endpoint,
            cfg.s3_access_key,
            cfg.s3_secret_key,
            cfg.s3_bucket,
            cfg.s3_region,
        ),
    }
    all_ok = all(dep["ok"] for dep in dependencies.values())
    return {"dependencies": dependencies, "all_ok": all_ok}


def run_healthcheck_cli() -> int:
    """Print dependency status and return 0 when healthy, 1 otherwise."""
    result = check_dependencies()
    for name, status in result["dependencies"].items():
        label = "ok" if status["ok"] else "FAIL"
        print(f"{name}: {label} — {status['detail']}")
    return 0 if result["all_ok"] else 1
