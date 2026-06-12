from datetime import datetime, timezone

from starscream.db.models import LicenseType
from starscream.pipeline.enrich import _derive_season
from starscream.pipeline.fingerprint import compute_spectral_hash
from starscream.pipeline.validate import validate_recording


def test_spectral_hash_no_audio():
    h = compute_spectral_hash(None)
    assert len(h) == 64


def test_validate_rejects_bad_lat():
    result = validate_recording(
        lat=999,
        lng=0,
        recorded_at=datetime.now(timezone.utc),
        license=LicenseType.CC0,
        audio_bytes=None,
        external_url=None,
    )
    assert not result.ok
    assert "latitude" in result.errors[0]


def test_derive_season_northern_summer():
    recorded = datetime(2024, 7, 15, tzinfo=timezone.utc)
    assert _derive_season(recorded, 45.0).value == "summer"


def test_derive_season_southern_summer():
    recorded = datetime(2024, 1, 15, tzinfo=timezone.utc)
    assert _derive_season(recorded, -45.0).value == "summer"
