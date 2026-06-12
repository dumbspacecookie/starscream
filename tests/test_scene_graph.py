import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from starscream.contrib.schema import (
    ContributionManifest,
    SceneEntity,
    SceneGraph,
    SoundEvent,
)
from starscream.contrib.validator import validate_contribution
from starscream.export.records import recording_to_row

TEMPLATE = Path(__file__).parent.parent / "starscream" / "contrib" / "templates" / "manifest.example.json"


def _make_wav_bytes(duration_s: float = 1.0, sr: int = 48000) -> bytes:
    import io

    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    audio = 0.1 * np.sin(2 * np.pi * 440 * t)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_sound_event_requires_end_after_start():
    with pytest.raises(ValueError, match="t_end_s"):
        SoundEvent(
            t_start_s=0.5,
            t_end_s=0.5,
            source_object="door",
            source_action="closing",
        )


def test_scene_graph_unique_entity_ids():
    with pytest.raises(ValueError, match="unique"):
        SceneGraph(
            entities=[
                SceneEntity(id="a", label="door", category="furniture"),
                SceneEntity(id="a", label="latch", category="hardware"),
            ]
        )


def test_manifest_backward_compatible_without_scene_fields():
    data = json.loads(TEMPLATE.read_text())
    del data["events"]
    del data["scene_graph"]
    manifest = ContributionManifest.model_validate(data)
    assert manifest.events is None
    assert manifest.scene_graph is None


def test_manifest_parses_events_and_scene_graph():
    manifest = ContributionManifest.model_validate(json.loads(TEMPLATE.read_text()))
    assert manifest.events is not None
    assert len(manifest.events) == 1
    assert manifest.events[0].entity_id == "door_1"
    assert manifest.scene_graph is not None
    assert len(manifest.scene_graph.entities) == 2
    assert manifest.scene_graph.events[0].entity_id == "latch_1"


def test_validate_rejects_event_beyond_duration():
    manifest = ContributionManifest.model_validate(json.loads(TEMPLATE.read_text()))
    manifest = manifest.model_copy(
        update={
            "events": [
                SoundEvent(
                    t_start_s=0.0,
                    t_end_s=2.0,
                    source_object="door",
                    source_action="closing",
                )
            ]
        }
    )
    report = validate_contribution(manifest, _make_wav_bytes(duration_s=1.0), strict=True)
    assert not report.valid
    assert any("exceeds" in e and "duration" in e for e in report.errors)


def test_validate_rejects_invalid_entity_ref():
    manifest = ContributionManifest.model_validate(json.loads(TEMPLATE.read_text()))
    manifest = manifest.model_copy(
        update={
            "events": [
                SoundEvent(
                    t_start_s=0.0,
                    t_end_s=0.5,
                    source_object="door",
                    source_action="closing",
                    entity_id="missing_entity",
                )
            ]
        }
    )
    report = validate_contribution(manifest, _make_wav_bytes(), strict=True)
    assert not report.valid
    assert any("missing_entity" in e for e in report.errors)


def test_validate_accepts_valid_scene_graph():
    manifest = ContributionManifest.model_validate(json.loads(TEMPLATE.read_text()))
    report = validate_contribution(manifest, _make_wav_bytes(), strict=True)
    assert report.valid


def test_recording_to_row_includes_scene_fields():
    class FakeRecording:
        id = "00000000-0000-0000-0000-000000000002"
        title = "Door"
        description = None
        source_object = "door"
        source_action = "closing"
        taxonomy_code = "URBAN"
        tags = []
        material = "wood"
        environment = "indoor"
        location_name = None
        country_code = None
        altitude_m = None
        recorded_at = __import__("datetime").datetime(
            2024, 1, 1, tzinfo=__import__("datetime").timezone.utc
        )
        season = None
        habitat = None
        license = type("L", (), {"value": "CC0"})()
        duration_s = 1.0
        sample_rate_hz = 48000
        channels = 1
        bit_depth = 16
        recorder_type = type("R", (), {"value": "smartphone"})()
        recorder_model = None
        contributor_id = None
        contributor_name = None
        spectral_hash = "abc"
        is_contribution = True
        world_model_labels = {}
        events = [{"t_start_s": 0.0, "t_end_s": 0.5, "source_object": "door", "source_action": "close"}]
        scene_graph = {"entities": [], "events": []}

    row = recording_to_row(FakeRecording(), 40.0, -73.0, None, "train")
    assert len(row["events"]) == 1
    assert row["scene_graph"]["entities"] == []
