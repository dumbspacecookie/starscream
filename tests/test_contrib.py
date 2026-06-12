import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from starscream.contrib.schema import ContributionManifest, PhysicalProperties
from starscream.contrib.validator import validate_contribution

TEMPLATE = Path(__file__).parent.parent / "starscream" / "contrib" / "templates" / "manifest.example.json"


def _make_wav_bytes(duration_s: float = 1.0, sr: int = 48000) -> bytes:
    import io

    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    audio = 0.1 * np.sin(2 * np.pi * 440 * t)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_manifest_from_template():
    data = json.loads(TEMPLATE.read_text())
    manifest = ContributionManifest.model_validate(data)
    assert manifest.source_object
    assert manifest.physical_properties is not None
    assert manifest.license.value in ("CC0", "CC-BY")


def test_manifest_rejects_lossy_filename():
    data = json.loads(TEMPLATE.read_text())
    data["audio_filename"] = "clip.mp3"
    with pytest.raises(ValueError, match="lossless"):
        ContributionManifest.model_validate(data)


def test_manifest_rejects_nc_license():
    data = json.loads(TEMPLATE.read_text())
    data["license"] = "CC-BY-NC"
    with pytest.raises(ValueError, match="CC0 or CC-BY"):
        ContributionManifest.model_validate(data)


def test_tags_normalized():
    data = json.loads(TEMPLATE.read_text())
    data["tags"] = ["Wood Door", "indoor", "wood door"]
    manifest = ContributionManifest.model_validate(data)
    assert "wood_door" in manifest.tags
    assert len(manifest.tags) == 2  # wood_door deduped


def test_validate_valid_contribution():
    manifest = ContributionManifest.model_validate(json.loads(TEMPLATE.read_text()))
    report = validate_contribution(manifest, _make_wav_bytes(), strict=True)
    assert report.valid
    assert report.duration_s is not None
    assert report.detected_sample_rate_hz == 48000


def test_validate_rejects_missing_audio():
    manifest = ContributionManifest.model_validate(json.loads(TEMPLATE.read_text()))
    report = validate_contribution(manifest, None, strict=True)
    assert not report.valid
    assert any("raw audio" in e for e in report.errors)


def test_validate_rejects_missing_physical_properties():
    manifest = ContributionManifest.model_validate(json.loads(TEMPLATE.read_text()))
    manifest = manifest.model_copy(update={"physical_properties": None})
    report = validate_contribution(manifest, _make_wav_bytes(), strict=True)
    assert not report.valid
    assert any("physical_properties" in e for e in report.errors)


def test_physical_properties_schema():
    props = PhysicalProperties(
        object_category="wildlife",
        interaction_type="vocalization",
        estimated_size="small",
    )
    assert props.interaction_type == "vocalization"


def test_api_guidelines_endpoint():
    from fastapi.testclient import TestClient

    from starscream.api.main import app

    client = TestClient(app)
    response = client.get("/v1/contrib/guidelines")
    assert response.status_code == 200
    body = response.json()
    assert "world models" in body["mission"].lower()
    assert "audio_requirements" in body
