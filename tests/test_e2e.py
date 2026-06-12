"""End-to-end test: upload → Postgres+PostGIS → S3 → Meilisearch → search.

Requires Docker Desktop / engine. Skipped when Docker or testcontainers is unavailable.
This is the proof test for v0.1 — see docs/V0.1_SCOPE.md.
"""

from __future__ import annotations

import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from starscream.api.geo import location_lat, location_lng
from tests.e2e_fixtures import MANIFEST_TEMPLATE, clear_e2e_caches, make_wav_bytes, register_e2e_contributor

pytestmark = pytest.mark.integration


def test_e2e_upload_store_search(e2e_stack):
    from starscream.api.main import app
    from starscream.config import get_settings
    from starscream.db.models import Recording
    from starscream.db.session import get_session_factory
    from starscream.health import check_dependencies
    from starscream.storage import get_audio_bytes

    clear_e2e_caches()
    settings = get_settings()

    health = check_dependencies(settings)
    assert health["all_ok"], health["dependencies"]

    client = TestClient(app)
    auth = register_e2e_contributor(client)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    unique = uuid.uuid4().hex[:8]
    manifest = json.loads(MANIFEST_TEMPLATE.read_text(encoding="utf-8"))
    manifest["title"] = f"E2E door close {unique}"
    manifest["audio_filename"] = "e2e_door.wav"
    manifest["tags"] = [f"e2e_{unique}", "door"]

    wav_bytes = make_wav_bytes()
    upload = client.post(
        "/v1/contrib/upload",
        data={"manifest_json": json.dumps(manifest)},
        files={"audio": ("e2e_door.wav", wav_bytes, "audio/wav")},
        headers=auth,
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    recording_id = body["recording"]["id"]
    assert body["recording"]["has_audio"] is True
    assert body["recording"]["spectral_hash"]

    session = get_session_factory()()
    try:
        lat_col = location_lat(Recording.location).label("lat")
        lng_col = location_lng(Recording.location).label("lng")
        row = session.execute(
            select(Recording, lat_col, lng_col).where(Recording.id == recording_id)
        ).one()
        rec, lat, lng = row
        assert rec.flac_key is not None
        assert rec.title == manifest["title"]
        assert float(lat) == pytest.approx(manifest["location"]["lat"], rel=1e-4)
        assert float(lng) == pytest.approx(manifest["location"]["lng"], rel=1e-4)

        spatial = session.execute(
            text(
                """
                SELECT COUNT(*) FROM recordings
                WHERE ST_DWithin(
                    location::geography,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                    :radius_m
                )
                AND id = :rid
                """
            ),
            {
                "lng": manifest["location"]["lng"],
                "lat": manifest["location"]["lat"],
                "radius_m": 5000,
                "rid": str(recording_id),
            },
        ).scalar_one()
        assert spatial == 1
    finally:
        session.close()

    stored = get_audio_bytes(rec.flac_key)
    assert stored is not None
    assert len(stored) > 0

    found = False
    for _ in range(30):
        search = client.get("/v1/search", params={"q": unique, "limit": 5})
        assert search.status_code == 200
        hits = search.json().get("hits", [])
        if any(h["id"] == recording_id for h in hits):
            found = True
            break
        time.sleep(0.5)
    assert found, "recording not found in Meilisearch after upload"


def test_e2e_dedup(e2e_stack):
    from starscream.api.main import app

    clear_e2e_caches()
    client = TestClient(app)
    auth = register_e2e_contributor(client)

    unique = uuid.uuid4().hex[:8]
    wav_bytes = make_wav_bytes(freq_hz=880.0)

    manifest_first = json.loads(MANIFEST_TEMPLATE.read_text(encoding="utf-8"))
    manifest_first["title"] = f"E2E dedup first {unique}"
    manifest_first["audio_filename"] = "e2e_dedup.wav"
    manifest_first["tags"] = [f"e2e_dedup_{unique}"]

    first = client.post(
        "/v1/contrib/upload",
        data={"manifest_json": json.dumps(manifest_first)},
        files={"audio": ("e2e_dedup.wav", wav_bytes, "audio/wav")},
        headers=auth,
    )
    assert first.status_code == 201, first.text
    first_body = first.json()["recording"]
    first_id = first_body["id"]
    assert first_body["canonical_id"] is None
    assert first_body["is_duplicate"] is False

    manifest_second = json.loads(MANIFEST_TEMPLATE.read_text(encoding="utf-8"))
    manifest_second["title"] = f"E2E dedup second {unique}"
    manifest_second["audio_filename"] = "e2e_dedup_copy.wav"
    manifest_second["tags"] = [f"e2e_dedup_{unique}", "duplicate"]

    second = client.post(
        "/v1/contrib/upload",
        data={"manifest_json": json.dumps(manifest_second)},
        files={"audio": ("e2e_dedup_copy.wav", wav_bytes, "audio/wav")},
        headers=auth,
    )
    assert second.status_code == 201, second.text
    second_body = second.json()["recording"]
    assert second_body["id"] != first_id
    assert second_body["canonical_id"] == first_id
    assert second_body["is_duplicate"] is True


def test_e2e_spatial_near(e2e_stack):
    from starscream.api.main import app

    clear_e2e_caches()
    client = TestClient(app)
    auth = register_e2e_contributor(client)

    unique = uuid.uuid4().hex[:8]
    manifest = json.loads(MANIFEST_TEMPLATE.read_text(encoding="utf-8"))
    manifest["title"] = f"E2E spatial {unique}"
    manifest["audio_filename"] = "e2e_spatial.wav"
    manifest["tags"] = [f"e2e_spatial_{unique}"]

    lat = manifest["location"]["lat"]
    lng = manifest["location"]["lng"]

    upload = client.post(
        "/v1/contrib/upload",
        data={"manifest_json": json.dumps(manifest)},
        files={"audio": ("e2e_spatial.wav", make_wav_bytes(), "audio/wav")},
        headers=auth,
    )
    assert upload.status_code == 201, upload.text
    recording_id = upload.json()["recording"]["id"]

    nearby = client.get(
        "/v1/recordings",
        params={"near": f"{lat},{lng}", "radius_km": 5, "limit": 100},
    )
    assert nearby.status_code == 200
    ids = {item["id"] for item in nearby.json()["items"]}
    assert recording_id in ids

    far = client.get(
        "/v1/recordings",
        params={"near": "0,0", "radius_km": 1, "limit": 100},
    )
    assert far.status_code == 200
    far_ids = {item["id"] for item in far.json()["items"]}
    assert recording_id not in far_ids
