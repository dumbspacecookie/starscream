"""Replicate primary S3 objects to secondary endpoints (R2, B2, Wasabi, etc.)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError

from starscream.config import get_settings
from starscream.storage.s3 import get_object_bytes

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MirrorEndpoint:
    name: str
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    region: str = "us-east-1"


def get_mirrors() -> list[MirrorEndpoint]:
    """Return configured secondary S3-compatible endpoints."""
    settings = get_settings()
    mirrors: list[MirrorEndpoint] = []
    for entry in settings.mirror_endpoints:
        mirrors.append(
            MirrorEndpoint(
                name=entry["name"],
                endpoint=entry["endpoint"],
                access_key=entry["access_key"],
                secret_key=entry["secret_key"],
                bucket=entry.get("bucket", settings.s3_bucket),
                region=entry.get("region", settings.s3_region),
            )
        )
    return mirrors


def _mirror_client(mirror: MirrorEndpoint):
    return boto3.client(
        "s3",
        endpoint_url=mirror.endpoint,
        aws_access_key_id=mirror.access_key,
        aws_secret_access_key=mirror.secret_key,
        region_name=mirror.region,
    )


def replicate_object(key: str, *, content_type: str | None = None) -> dict[str, bool | str]:
    """Copy an object from the primary bucket to every configured mirror.

    Returns a mapping of mirror name (or ``primary``) to success flag or error message.
    """
    data = get_object_bytes(key)
    if data is None:
        return {"primary": False, "error": f"object not found: {key}"}

    mirrors = get_mirrors()
    if not mirrors:
        logger.debug("No mirror endpoints configured; skipping replication for %s", key)
        return {"primary": True, "mirrors": 0}

    results: dict[str, bool | str] = {"primary": True}
    extra: dict[str, str] = {}
    if content_type:
        extra["ContentType"] = content_type

    for mirror in mirrors:
        try:
            _mirror_client(mirror).put_object(
                Bucket=mirror.bucket,
                Key=key,
                Body=data,
                **extra,
            )
            results[mirror.name] = True
            logger.info("Replicated %s to mirror %s", key, mirror.name)
        except ClientError as exc:
            msg = str(exc)
            results[mirror.name] = msg
            logger.warning("Mirror %s failed for %s: %s", mirror.name, key, msg)

    return results
