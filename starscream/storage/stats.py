"""Object storage usage helpers."""

from __future__ import annotations

import logging

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from starscream.config import get_settings

logger = logging.getLogger(__name__)

_FAST_CONFIG = Config(connect_timeout=1, read_timeout=2, retries={"max_attempts": 1})


def flac_storage_bytes() -> int:
    """Sum byte size of all objects under the flac/ prefix."""
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=_FAST_CONFIG,
    )
    total = 0
    try:
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=settings.s3_bucket, Prefix="flac/"):
            for obj in page.get("Contents", []):
                total += int(obj.get("Size", 0))
    except (ClientError, OSError, Exception) as exc:
        logger.warning("Could not list FLAC objects for stats: %s", exc)
        return 0
    return total
