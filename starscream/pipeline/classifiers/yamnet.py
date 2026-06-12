"""YAMNet audio event classifier — tensorflow-hub or librosa spectral fallback."""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

MODEL_NAME = "yamnet"

# Subset of YAMNet labels mapped to Starscream taxonomy branches.
LABEL_TAXONOMY: dict[str, str] = {
    "Bird": "WILDLIFE.BIRD",
    "Bird vocalization, bird call, bird song": "WILDLIFE.BIRD",
    "Chirp, tweet": "WILDLIFE.BIRD",
    "Crow": "WILDLIFE.BIRD",
    "Owl": "WILDLIFE.BIRD",
    "Pigeon, dove": "WILDLIFE.BIRD",
    "Canidae, dogs, wolves": "WILDLIFE.MAMMAL",
    "Dog": "WILDLIFE.MAMMAL",
    "Bark": "WILDLIFE.MAMMAL",
    "Cat": "WILDLIFE.MAMMAL",
    "Meow": "WILDLIFE.MAMMAL",
    "Insect": "WILDLIFE.INSECT",
    "Cricket": "WILDLIFE.INSECT",
    "Rain": "ATMOSPHERIC.RAIN",
    "Thunder": "ATMOSPHERIC.THUNDER",
    "Thunderstorm": "ATMOSPHERIC.THUNDER",
    "Wind": "NATURAL.WIND",
    "Ocean": "NATURAL.OCEAN",
    "Waves, surf": "NATURAL.OCEAN",
    "Vehicle": "URBAN.TRAFFIC",
    "Car": "URBAN.TRAFFIC",
    "Traffic noise, roadway noise": "URBAN.TRAFFIC",
    "Engine": "MECHANICAL",
    "Music": "CULTURAL",
    "Speech": "HUMAN.SPEECH",
    "Child speech, kid speaking": "HUMAN.SPEECH",
    "Door": "DOMESTIC",
    "Knock": "DOMESTIC",
}

@dataclass(frozen=True)
class YamnetPrediction:
    label: str
    confidence: float
    taxonomy_suggestion: str | None


def _taxonomy_for_label(label: str) -> str | None:
    if label in LABEL_TAXONOMY:
        return LABEL_TAXONOMY[label]
    lower = label.lower()
    for key, code in LABEL_TAXONOMY.items():
        if key.lower() in lower or lower in key.lower():
            return code
    return None


def _load_class_names(class_map_path: bytes | str) -> list[str]:
    text = class_map_path.decode("utf-8") if isinstance(class_map_path, bytes) else class_map_path
    reader = csv.DictReader(io.StringIO(text))
    names: list[str] = []
    for row in reader:
        display = row.get("display_name") or row.get("name") or ""
        names.append(display)
    return names


def _classify_yamnet_tf(audio_bytes: bytes, *, top_k: int) -> list[YamnetPrediction] | None:
    try:
        import librosa
        import tensorflow as tf
        import tensorflow_hub as hub
    except ImportError:
        return None

    try:
        model = hub.load("https://tfhub.dev/google/yamnet/1")
        y, _sr = librosa.load(io.BytesIO(audio_bytes), sr=16000, mono=True)
        if len(y) == 0:
            return []

        waveform = tf.constant(y, dtype=tf.float32)
        scores, _, _ = model(waveform)
        mean_scores = tf.reduce_mean(scores, axis=0).numpy()

        class_map_path = model.class_map_path().numpy()
        class_names = _load_class_names(class_map_path)
        if not class_names:
            return []

        top_indices = np.argsort(mean_scores)[::-1][:top_k]
        predictions: list[YamnetPrediction] = []
        for idx in top_indices:
            score = float(mean_scores[idx])
            if score < 0.01:
                continue
            label = class_names[idx] if idx < len(class_names) else f"class_{idx}"
            predictions.append(
                YamnetPrediction(
                    label=label,
                    confidence=score,
                    taxonomy_suggestion=_taxonomy_for_label(label),
                )
            )
        return predictions
    except Exception as exc:
        logger.debug("YAMNet TF classification failed: %s", exc)
        return None


def _classify_yamnet_fallback(audio_bytes: bytes, *, top_k: int) -> list[YamnetPrediction]:
    """Lightweight spectral heuristic when tensorflow-hub is not installed."""
    try:
        import librosa
    except ImportError:
        return []

    try:
        y, sr = librosa.load(io.BytesIO(audio_bytes), sr=22050, mono=True)
        if len(y) == 0:
            return []

        centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
        rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))
        zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)))
        rms = float(np.mean(librosa.feature.rms(y=y)))
        flatness = float(np.mean(librosa.feature.spectral_flatness(y=y)))

        candidates: list[tuple[str, float, str | None]] = []

        if 1500 < centroid < 9000 and zcr > 0.04 and flatness < 0.3:
            candidates.append(("Bird vocalization (spectral heuristic)", 0.35, "WILDLIFE.BIRD"))
        if centroid < 1200 and rms > 0.02 and zcr < 0.08:
            candidates.append(("Engine / motor (spectral heuristic)", 0.3, "MECHANICAL"))
        if centroid < 800 and rolloff < 2000 and rms > 0.01:
            candidates.append(("Traffic / vehicle (spectral heuristic)", 0.28, "URBAN.TRAFFIC"))
        if flatness > 0.4 and rms > 0.005:
            candidates.append(("Wind / noise (spectral heuristic)", 0.25, "NATURAL.WIND"))
        if 800 < centroid < 3000 and zcr > 0.1:
            candidates.append(("Speech-like (spectral heuristic)", 0.22, "HUMAN.SPEECH"))
        if not candidates:
            candidates.append(("Ambient sound (spectral heuristic)", 0.15, "NATURAL"))

        candidates.sort(key=lambda item: item[1], reverse=True)
        return [
            YamnetPrediction(label=label, confidence=conf, taxonomy_suggestion=tax)
            for label, conf, tax in candidates[:top_k]
        ]
    except Exception as exc:
        logger.debug("YAMNet fallback classification failed: %s", exc)
        return []


def classify_yamnet(audio_bytes: bytes, *, top_k: int = 5) -> list[YamnetPrediction]:
    if not audio_bytes:
        return []

    tf_results = _classify_yamnet_tf(audio_bytes, top_k=top_k)
    if tf_results is not None:
        return tf_results
    return _classify_yamnet_fallback(audio_bytes, top_k=top_k)
