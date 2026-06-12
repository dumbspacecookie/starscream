"""Shared helpers for Docker-backed integration tests."""

from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_TEMPLATE = REPO_ROOT / "starscream" / "contrib" / "templates" / "manifest.example.json"


def _docker_available() -> bool:
    try:
        import docker

        docker.from_env().ping()
        return True
    except Exception:
        return False


def clear_e2e_caches() -> None:
    from starscream.config import get_settings
    from starscream.db.session import get_engine, get_session_factory

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def configure_compose_env() -> None:
    """Use services from `docker compose up -d` (dev compose file)."""
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+psycopg://starscream:starscream@localhost:5432/starscream",
    )
    os.environ.setdefault("MEILISEARCH_URL", "http://localhost:7700")
    os.environ.setdefault("MEILISEARCH_API_KEY", "")
    os.environ.setdefault("S3_ENDPOINT", "http://localhost:9000")
    os.environ.setdefault("S3_ACCESS_KEY", "starscream")
    os.environ.setdefault("S3_SECRET_KEY", "starscream")
    os.environ.setdefault("S3_BUCKET", "starscream-audio")
    os.environ.setdefault("S3_REGION", "us-east-1")
    os.environ["ENRICH_GEOCODE"] = "false"
    os.environ["ENRICH_HABITAT"] = "false"
    os.environ["ENRICH_WEATHER"] = "false"
    os.environ["ENRICH_OSM"] = "false"
    clear_e2e_caches()


def make_wav_bytes(duration_s: float = 1.0, sr: int = 48000, freq_hz: float = 440.0) -> bytes:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    audio = 0.1 * np.sin(2 * np.pi * freq_hz * t)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def register_e2e_contributor(client) -> dict[str, str]:
    """Register a contributor and return auth headers for upload tests."""
    import uuid

    name = f"E2E Tester {uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/v1/contrib/register",
        json={"display_name": name, "github_username": None},
    )
    assert resp.status_code == 201, resp.text
    api_key = resp.json()["api_key"]
    return {"X-API-Key": api_key}


def run_migrations() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade failed:\nstdout={result.stdout}\nstderr={result.stderr}"
        )
