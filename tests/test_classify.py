import io
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

from starscream.pipeline.classify import Classification, ClassificationSuggestion, classify_audio
from starscream.pipeline.classifiers.birdnet import BirdnetPrediction, classify_birdnet
from starscream.pipeline.classifiers.yamnet import YamnetPrediction, classify_yamnet


def _make_wav_bytes(duration_s: float = 0.5, sr: int = 16000, freq: float = 440.0) -> bytes:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    audio = 0.2 * np.sin(2 * np.pi * freq * t)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_classify_audio_empty_returns_no_suggestions():
    result = classify_audio(None, "WILDLIFE.BIRD")
    assert result.suggestions == []


def test_classify_audio_returns_ranked_suggestions():
    audio = _make_wav_bytes()
    result = classify_audio(audio, "NATURAL")
    assert isinstance(result, Classification)
    assert len(result.suggestions) > 0
    for item in result.suggestions:
        assert isinstance(item, ClassificationSuggestion)
        assert item.model_name in ("yamnet", "birdnet")
        assert item.label
        assert 0.0 <= item.confidence <= 1.0
    confidences = [item.confidence for item in result.suggestions]
    assert confidences == sorted(confidences, reverse=True)


def test_classify_audio_never_emits_user_taxonomy_as_authoritative():
    audio = _make_wav_bytes()
    result = classify_audio(audio, "URBAN.TRAFFIC")
    assert all(item.model_name in ("yamnet", "birdnet") for item in result.suggestions)
    assert all(item.confidence < 1.0 for item in result.suggestions)


def test_yamnet_fallback_produces_predictions_without_tf():
    audio = _make_wav_bytes(freq=3000.0)
    with patch(
        "starscream.pipeline.classifiers.yamnet._classify_yamnet_tf",
        return_value=None,
    ):
        preds = classify_yamnet(audio)
    assert len(preds) > 0
    assert all(isinstance(p, YamnetPrediction) for p in preds)


def test_birdnet_skips_gracefully_without_package():
    audio = _make_wav_bytes()
    with patch.dict("sys.modules", {"birdnetlib": None, "birdnet_analyzer": None}):
        preds = classify_birdnet(audio)
    assert preds == []


def test_classify_audio_with_mocked_classifiers():
    audio = _make_wav_bytes()
    yamnet_preds = [
        YamnetPrediction(label="Bird", confidence=0.8, taxonomy_suggestion="WILDLIFE.BIRD")
    ]
    birdnet_preds = [
        BirdnetPrediction(label="American Robin", confidence=0.6, taxonomy_suggestion="WILDLIFE.BIRD")
    ]

    with (
        patch("starscream.pipeline.classify.classify_yamnet", return_value=yamnet_preds),
        patch("starscream.pipeline.classify.classify_birdnet", return_value=birdnet_preds),
    ):
        result = classify_audio(audio, "NATURAL")

    assert len(result.suggestions) == 2
    assert result.suggestions[0].model_name == "yamnet"
    assert result.suggestions[0].confidence == pytest.approx(0.8)
    assert result.suggestions[1].model_name == "birdnet"
