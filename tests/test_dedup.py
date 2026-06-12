import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from starscream.pipeline.dedup import (
    QUALITY_FLAC,
    QUALITY_MP3,
    QUALITY_POINTER,
    audio_quality_tier,
    find_duplicate,
    link_duplicate,
    resolve_canonical,
)


def _recording(**kwargs) -> SimpleNamespace:
    """Build a duck-typed recording for unit tests."""
    defaults: dict = {
        "id": uuid.uuid4(),
        "spectral_hash": "abc123",
        "flac_key": None,
        "mp3_key": None,
        "external_url": None,
        "external_id": None,
        "canonical_id": None,
        "is_duplicate": False,
        "duration_s": None,
        "canonical": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_audio_quality_tier_flac_beats_mp3():
    assert audio_quality_tier(_recording(flac_key="flac/x.flac")) == QUALITY_FLAC
    assert audio_quality_tier(_recording(mp3_key="mp3/x.mp3")) == QUALITY_MP3
    assert audio_quality_tier(_recording(external_url="https://example.com/x")) == QUALITY_POINTER


def test_audio_quality_tier_flac_over_mp3():
    flac = _recording(flac_key="flac/a.flac", mp3_key="mp3/a.mp3")
    mp3_only = _recording(mp3_key="mp3/b.mp3")
    assert audio_quality_tier(flac) > audio_quality_tier(mp3_only)


def test_resolve_canonical_self_when_not_duplicate():
    rec = _recording()
    assert resolve_canonical(rec) is rec


def test_resolve_canonical_follows_chain():
    canonical_id = uuid.uuid4()
    canonical = _recording(id=canonical_id)
    dup = _recording(canonical_id=canonical_id, is_duplicate=True, canonical=canonical)
    assert resolve_canonical(dup) is canonical


def test_find_duplicate_returns_none_when_missing():
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    assert find_duplicate(db, "missing") is None


def test_find_duplicate_resolves_to_canonical():
    canonical_id = uuid.uuid4()
    canonical = _recording(id=canonical_id)
    dup = _recording(canonical_id=canonical_id, is_duplicate=True, canonical=canonical)
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = dup
    assert find_duplicate(db, "abc123") is canonical


def test_link_duplicate_sets_fields():
    canonical_id = uuid.uuid4()
    canonical = _recording(id=canonical_id, mp3_key="mp3/old.mp3")
    new = _recording(flac_key="flac/new.flac")
    db = MagicMock()
    link_duplicate(db, new, canonical)
    assert new.canonical_id == canonical_id
    assert new.is_duplicate is True


def test_link_duplicate_promotes_higher_quality_to_canonical():
    canonical_id = uuid.uuid4()
    canonical = _recording(id=canonical_id, mp3_key="mp3/old.mp3")
    new = _recording(flac_key="flac/new.flac", duration_s=2.5)
    db = MagicMock()
    link_duplicate(db, new, canonical)
    assert canonical.flac_key == "flac/new.flac"
    assert canonical.duration_s == 2.5


def test_link_duplicate_does_not_downgrade_canonical():
    canonical_id = uuid.uuid4()
    canonical = _recording(id=canonical_id, flac_key="flac/best.flac")
    new = _recording(mp3_key="mp3/worse.mp3")
    db = MagicMock()
    link_duplicate(db, new, canonical)
    assert canonical.flac_key == "flac/best.flac"
    assert new.is_duplicate is True


def test_link_duplicate_through_existing_duplicate():
    canonical_id = uuid.uuid4()
    canonical = _recording(id=canonical_id, external_url="https://x")
    first_dup = _recording(
        id=uuid.uuid4(),
        canonical_id=canonical_id,
        is_duplicate=True,
        mp3_key="mp3/first.mp3",
        canonical=canonical,
    )
    new = _recording(flac_key="flac/better.flac")
    db = MagicMock()
    link_duplicate(db, new, first_dup)
    assert new.canonical_id == canonical_id
    assert canonical.flac_key == "flac/better.flac"
