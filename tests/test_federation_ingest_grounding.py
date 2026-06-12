"""Federated ingest applies grounding + minimal world_model_labels."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from starscream.db.models import LicenseType
from starscream.federation.base import FederatedRecord
from starscream.federation.ingest import ingest_federated_records


@patch("starscream.federation.ingest.get_broadcaster")
@patch("starscream.federation.ingest.index_recording")
@patch("starscream.federation.ingest.persist_classifications")
@patch("starscream.federation.ingest.classify_audio")
@patch("starscream.federation.ingest.enrich_metadata")
@patch("starscream.federation.ingest.compute_spectral_hash", return_value="hash-ground")
@patch("starscream.federation.ingest.find_duplicate", return_value=None)
@patch("starscream.federation.ingest.link_cross_source_duplicates")
def test_ingest_grounds_weak_fields_and_sets_wm_labels(
    _link_cross,
    _find_dup,
    _hash,
    mock_enrich,
    mock_classify,
    _persist,
    _index,
    _broadcaster,
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

    source = SimpleNamespace(id=uuid.uuid4(), slug="internet-archive", record_count=0)
    record = FederatedRecord(
        external_id="ia-rain",
        external_url="https://archive.org/details/rain",
        taxonomy_code="ATMOSPHERIC.RAIN",
        lat=0.0,
        lng=0.0,
        recorded_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        license="CC0",
        title="Rain on tin roof",
        tags=["rain", "storm"],
        source_object="Rain on tin roof",
        source_action="producing sound",
    )

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None

    result = ingest_federated_records(db, source, [record], download_audio=False)

    assert result.created == 1
    added = db.add.call_args[0][0]
    assert added.source_action == "falling"
    assert added.world_model_labels["object_category"] == "environment"
    assert added.world_model_labels["interaction_type"] == "falling"
    assert added.license == LicenseType.CC0
