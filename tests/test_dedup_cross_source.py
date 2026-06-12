import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from starscream.api.main import app
from starscream.db.models import LicenseType
from starscream.federation.base import FederatedRecord
from starscream.federation.ingest import ingest_federated_records
from starscream.pipeline.dedup import (
    get_canonical_chain,
    link_cross_source_duplicates,
)


def _recording(**kwargs) -> SimpleNamespace:
    defaults: dict = {
        "id": uuid.uuid4(),
        "spectral_hash": "hash-abc",
        "source_id": uuid.uuid4(),
        "flac_key": None,
        "mp3_key": None,
        "external_url": None,
        "external_id": None,
        "canonical_id": None,
        "is_duplicate": False,
        "duration_s": None,
        "canonical": None,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_link_cross_source_no_peers_returns_resolved_self():
    rec = _recording()
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    result = link_cross_source_duplicates(db, rec)
    assert result is rec


def test_link_cross_source_links_lower_quality_peer():
    source_a = uuid.uuid4()
    source_b = uuid.uuid4()
    canonical_id = uuid.uuid4()
    peer_id = uuid.uuid4()

    canonical = _recording(
        id=canonical_id,
        source_id=source_a,
        flac_key="flac/canonical.flac",
        mp3_key=None,
    )
    peer = _recording(
        id=peer_id,
        source_id=source_b,
        external_url="https://example.com/audio",
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = [peer]

    link_cross_source_duplicates(db, canonical)

    assert peer.canonical_id == canonical_id
    assert peer.is_duplicate is True
    assert canonical.canonical_id is None


def test_link_cross_source_promotes_better_quality_to_canonical():
    source_a = uuid.uuid4()
    source_b = uuid.uuid4()
    pointer_id = uuid.uuid4()
    flac_id = uuid.uuid4()

    pointer = _recording(
        id=pointer_id,
        source_id=source_a,
        external_url="https://xeno.example/1",
    )
    flac_rec = _recording(
        id=flac_id,
        source_id=source_b,
        flac_key="flac/new.flac",
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = [pointer]

    link_cross_source_duplicates(db, flac_rec)

    assert pointer.canonical_id == flac_id
    assert pointer.is_duplicate is True
    assert flac_rec.canonical_id is None


def test_get_canonical_chain_returns_canonical_and_alternates():
    canonical_id = uuid.uuid4()
    alt_id = uuid.uuid4()
    canonical = _recording(id=canonical_id)
    alt = _recording(id=alt_id, canonical_id=canonical_id, is_duplicate=True)
    dup = _recording(canonical_id=canonical_id, is_duplicate=True, canonical=canonical)

    db = MagicMock()
    db.scalars.return_value.all.return_value = [alt]

    resolved, alternates = get_canonical_chain(db, dup)
    assert resolved is canonical
    assert alternates == [alt]


@patch("starscream.federation.ingest.index_recording")
@patch("starscream.federation.ingest.persist_classifications")
@patch("starscream.federation.ingest.classify_audio")
@patch("starscream.federation.ingest.enrich_metadata")
@patch("starscream.federation.ingest.compute_spectral_hash", return_value="hash-nc")
@patch("starscream.federation.ingest.find_duplicate", return_value=None)
@patch("starscream.federation.ingest.link_cross_source_duplicates")
@patch("starscream.federation.ingest.put_audio")
def test_ingest_cc_by_nc_pointer_only_no_audio(
    mock_put_audio,
    mock_link_cross,
    mock_find_dup,
    mock_hash,
    mock_enrich,
    mock_classify,
    mock_persist,
    mock_index,
    caplog,
):
    mock_enrich.return_value = SimpleNamespace(
        location_name=None,
        country_code=None,
        season=None,
        habitat=None,
        weather=None,
        temperature_c=None,
        cross_modal_links=None,
    )
    mock_classify.return_value = []

    source = SimpleNamespace(id=uuid.uuid4(), slug="xeno-canto", record_count=0)
    record = FederatedRecord(
        external_id="xc123",
        external_url="https://xeno-canto.org/123",
        taxonomy_code="WILDLIFE.BIRD",
        lat=40.0,
        lng=-73.0,
        recorded_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        license="CC-BY-NC",
    )
    record._preview_bytes = b"fake-audio-should-not-store"

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None

    with caplog.at_level("WARNING"):
        result = ingest_federated_records(db, source, [record])

    assert result.created == 1
    mock_put_audio.assert_not_called()
    added = db.add.call_args[0][0]
    assert added.license == LicenseType.POINTER_ONLY
    assert added.flac_key is None
    assert added.mp3_key is None
    assert "pointer-only storage" in caplog.text


def _full_mock_recording(rec_id: uuid.UUID):
    rec = MagicMock()
    rec.id = rec_id
    rec.spectral_hash = "hash-xyz"
    rec.taxonomy_code = "WILDLIFE.BIRD"
    rec.recorded_at = datetime(2024, 6, 15, tzinfo=timezone.utc)
    rec.source_id = uuid.uuid4()
    rec.license = "CC0"
    rec.title = "Robin"
    rec.description = None
    rec.source_object = None
    rec.source_action = None
    rec.tags = []
    rec.material = None
    rec.environment = None
    rec.world_model_labels = None
    rec.contributor_id = None
    rec.contributor_name = None
    rec.recorder_model = None
    rec.sample_rate_hz = None
    rec.channels = None
    rec.bit_depth = None
    rec.is_contribution = False
    rec.location_name = None
    rec.country_code = None
    rec.altitude_m = None
    rec.season = None
    rec.habitat = None
    rec.weather = None
    rec.temperature_c = None
    rec.cross_modal_links = None
    rec.recorder_type = "unknown"
    rec.quality = None
    rec.review_status = "unreviewed"
    rec.external_id = "ext-1"
    rec.external_url = None
    rec.duration_s = 1.0
    rec.flac_key = None
    rec.mp3_key = None
    rec.canonical_id = None
    rec.is_duplicate = False
    return rec


@patch("starscream.api.routes.recordings.get_canonical_chain")
def test_canonical_endpoint_returns_chain(mock_chain):
    recording_id = uuid.uuid4()
    canonical_id = uuid.uuid4()
    alt_id = uuid.uuid4()

    recording = _full_mock_recording(recording_id)
    canonical = _full_mock_recording(canonical_id)
    alternate = _full_mock_recording(alt_id)
    alternate.canonical_id = canonical_id
    alternate.is_duplicate = True

    mock_chain.return_value = (canonical, [alternate])

    main_row = (recording, 40.0, -73.0)
    canon_row = (canonical, 41.0, -74.0)
    alt_row = (alternate, 42.0, -75.0)

    mock_execute = MagicMock()
    mock_execute.one_or_none.return_value = main_row
    mock_execute.one.return_value = canon_row
    mock_execute.all.return_value = [alt_row]

    mock_db = MagicMock()
    mock_db.execute.return_value = mock_execute

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        response = client.get(f"/v1/recordings/{recording_id}/canonical")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["recording_id"] == str(recording_id)
    assert data["canonical"]["id"] == str(canonical_id)
    assert len(data["alternates"]) == 1
    assert data["alternates"][0]["id"] == str(alt_id)


def test_canonical_endpoint_404_when_missing():
    mock_db = MagicMock()
    mock_db.execute.return_value.one_or_none.return_value = None

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        response = client.get(f"/v1/recordings/{uuid.uuid4()}/canonical")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
