import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from starscream.api.main import app
from starscream.db.models import Recording
from starscream.pipeline.similar import find_similar_recordings, score_similarity


def _recording(**kwargs) -> SimpleNamespace:
    defaults: dict = {
        "id": uuid.uuid4(),
        "taxonomy_code": "HUMAN.MADE.DOOR",
        "tags": ["door", "indoor"],
        "material": "wood",
        "source_object": "wooden door",
        "location": object(),
        "recorded_at": datetime(2024, 6, 15, tzinfo=timezone.utc),
        "is_duplicate": False,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_score_taxonomy_prefix():
    source = _recording(taxonomy_code="HUMAN.MADE.DOOR", tags=[], material=None, source_object=None)
    candidate = _recording(taxonomy_code="HUMAN.MADE.WINDOW", tags=[], material=None, source_object=None)
    assert score_similarity(source, candidate, within_50km=False) == 3


def test_score_shared_tags():
    source = _recording(tags=["door", "wood"], taxonomy_code="A.B", material=None, source_object=None)
    candidate = _recording(tags=["door", "metal"], taxonomy_code="X.Y", material=None, source_object=None)
    assert score_similarity(source, candidate, within_50km=False) == 2


def test_score_same_material():
    source = _recording(material="wood", taxonomy_code="A", tags=[], source_object=None)
    candidate = _recording(material="wood", taxonomy_code="B", tags=[], source_object=None)
    assert score_similarity(source, candidate, within_50km=False) == 2


def test_score_source_object_word_overlap():
    source = _recording(source_object="wooden door frame", taxonomy_code="A", tags=[], material=None)
    candidate = _recording(source_object="metal door", taxonomy_code="B", tags=[], material=None)
    assert score_similarity(source, candidate, within_50km=False) == 1


def test_score_within_50km_bonus():
    source = _recording(taxonomy_code="A", tags=[], material=None, source_object=None)
    candidate = _recording(taxonomy_code="B", tags=[], material=None, source_object=None)
    assert score_similarity(source, candidate, within_50km=True) == 2
    assert score_similarity(source, candidate, within_50km=False) == 0


def test_score_combined():
    source = _recording(
        taxonomy_code="HUMAN.MADE.DOOR",
        tags=["door"],
        material="wood",
        source_object="wooden door",
    )
    candidate = _recording(
        taxonomy_code="HUMAN.MADE.WINDOW",
        tags=["door", "glass"],
        material="wood",
        source_object="wooden window",
    )
    # prefix +3, tag door +2, material +2, word wood +1, geo +2 = 10
    assert score_similarity(source, candidate, within_50km=True) == 10


def test_find_similar_recordings_excludes_self_and_duplicates():
    source_id = uuid.uuid4()
    source = _recording(id=source_id)
    good = _recording(
        id=uuid.uuid4(),
        taxonomy_code="HUMAN.MADE.WINDOW",
        tags=[],
        material=None,
        source_object=None,
    )
    duplicate = _recording(id=uuid.uuid4(), is_duplicate=True, taxonomy_code="HUMAN.MADE.WINDOW")

    db = MagicMock()
    db.execute.return_value.all.side_effect = [
        [(good, 40.0, -73.0), (duplicate, 41.0, -74.0), (source, 40.0, -73.0)],
        [(good.id,)],
    ]

    results = find_similar_recordings(db, source, limit=10)
    assert len(results) == 1
    assert results[0][0] is good
    assert results[0][3] == 5  # prefix 3 + geo 2


def test_find_similar_recordings_respects_limit():
    source = _recording()
    candidates = [
        (_recording(taxonomy_code="HUMAN.MADE.WINDOW"), 40.0, -73.0),
        (_recording(taxonomy_code="HUMAN.MADE.GATE"), 41.0, -74.0),
        (_recording(taxonomy_code="HUMAN.MADE.FENCE"), 42.0, -75.0),
    ]

    db = MagicMock()
    db.execute.return_value.all.side_effect = [candidates, []]

    results = find_similar_recordings(db, source, limit=2)
    assert len(results) == 2


def test_similar_endpoint_in_openapi():
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/v1/recordings/{recording_id}/similar" in response.json()["paths"]


@patch("starscream.api.routes.recordings.find_similar_recordings")
def test_similar_endpoint_returns_matches(mock_find):
    recording_id = uuid.uuid4()
    match_id = uuid.uuid4()

    mock_recording = MagicMock(spec=Recording)
    mock_recording.id = match_id
    mock_recording.spectral_hash = "abc"
    mock_recording.taxonomy_code = "HUMAN.MADE.WINDOW"
    mock_recording.recorded_at = datetime(2024, 6, 15, tzinfo=timezone.utc)
    mock_recording.source_id = uuid.uuid4()
    mock_recording.license = "CC0"
    mock_recording.title = "Window creak"
    mock_recording.description = None
    mock_recording.source_object = "window"
    mock_recording.source_action = None
    mock_recording.tags = ["window"]
    mock_recording.material = "wood"
    mock_recording.environment = "indoor"
    mock_recording.world_model_labels = None
    mock_recording.contributor_id = None
    mock_recording.contributor_name = None
    mock_recording.recorder_model = None
    mock_recording.sample_rate_hz = None
    mock_recording.channels = None
    mock_recording.bit_depth = None
    mock_recording.is_contribution = True
    mock_recording.location_name = None
    mock_recording.country_code = "US"
    mock_recording.altitude_m = None
    mock_recording.season = None
    mock_recording.habitat = None
    mock_recording.weather = None
    mock_recording.temperature_c = None
    mock_recording.cross_modal_links = None
    mock_recording.recorder_type = "unknown"
    mock_recording.quality = 4
    mock_recording.review_status = "unreviewed"
    mock_recording.external_id = None
    mock_recording.external_url = None
    mock_recording.duration_s = 1.5
    mock_recording.flac_key = "flac/x.flac"
    mock_recording.canonical_id = None
    mock_recording.is_duplicate = False

    mock_find.return_value = [(mock_recording, 40.758, -73.985, 5)]

    mock_db = MagicMock()
    source = MagicMock(spec=Recording)
    mock_db.get.return_value = source

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        response = client.get(f"/v1/recordings/{recording_id}/similar", params={"limit": 5})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["recording_id"] == str(recording_id)
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(match_id)
    assert data["items"][0]["taxonomy_code"] == "HUMAN.MADE.WINDOW"
    mock_find.assert_called_once_with(mock_db, source, limit=5)


def test_similar_endpoint_404_when_missing():
    mock_db = MagicMock()
    mock_db.get.return_value = None

    from starscream.db.session import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        response = client.get(f"/v1/recordings/{uuid.uuid4()}/similar")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
