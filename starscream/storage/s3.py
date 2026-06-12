"""Primary S3-compatible object storage helpers."""

import logging

import boto3
from botocore.exceptions import ClientError

from starscream.config import get_settings

logger = logging.getLogger(__name__)


def _client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )


def ensure_bucket() -> None:
    settings = get_settings()
    client = _client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        try:
            client.create_bucket(Bucket=settings.s3_bucket)
        except ClientError as exc:
            logger.warning("Could not create bucket %s: %s", settings.s3_bucket, exc)


def put_audio(key: str, data: bytes, content_type: str = "audio/flac") -> str | None:
    settings = get_settings()
    try:
        _client().put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key
    except ClientError as exc:
        logger.warning("Failed to store audio at %s: %s", key, exc)
        return None


def get_object_bytes(key: str) -> bytes | None:
    settings = get_settings()
    try:
        response = _client().get_object(Bucket=settings.s3_bucket, Key=key)
        return response["Body"].read()
    except ClientError:
        return None


def get_audio_bytes(key: str) -> bytes | None:
    return get_object_bytes(key)


def put_spectrogram(recording_id: str, data: bytes) -> str | None:
    key = f"spectrogram/{recording_id}.png"
    settings = get_settings()
    try:
        _client().put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=data,
            ContentType="image/png",
        )
        return key
    except ClientError as exc:
        logger.warning("Failed to store spectrogram at %s: %s", key, exc)
        return None


def get_spectrogram_bytes(key: str) -> bytes | None:
    return get_object_bytes(key)
