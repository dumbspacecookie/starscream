"""BirdNET species classifier — optional dependency, skips gracefully when absent."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_NAME = "birdnet"


@dataclass(frozen=True)
class BirdnetPrediction:
    label: str
    confidence: float
    taxonomy_suggestion: str | None = "WILDLIFE.BIRD"


def _analyze_with_birdnetlib(audio_bytes: bytes) -> list[BirdnetPrediction]:
    from birdnetlib import Recording
    from birdnetlib.analyzer import Analyzer

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        path = tmp.name

    try:
        analyzer = Analyzer()
        recording = Recording(
            analyzer,
            path,
            lat=0.0,
            lon=0.0,
            date=datetime.now(timezone.utc),
            min_conf=0.1,
        )
        recording.analyze()
        return [
            BirdnetPrediction(
                label=detection.common_name,
                confidence=float(detection.confidence),
                taxonomy_suggestion="WILDLIFE.BIRD",
            )
            for detection in recording.detections
        ]
    finally:
        Path(path).unlink(missing_ok=True)


def _analyze_with_birdnet_analyzer(audio_bytes: bytes) -> list[BirdnetPrediction]:
    import birdnet_analyzer as bna

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        path = tmp.name

    try:
        raw = bna.analyze(path, min_conf=0.1)
        predictions: list[BirdnetPrediction] = []
        for row in raw or []:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                label, conf = str(row[0]), float(row[1])
            elif isinstance(row, dict):
                label = str(row.get("common_name") or row.get("species") or row.get("label", ""))
                conf = float(row.get("confidence") or row.get("score") or 0.0)
            else:
                continue
            if label and conf >= 0.1:
                predictions.append(
                    BirdnetPrediction(
                        label=label,
                        confidence=conf,
                        taxonomy_suggestion="WILDLIFE.BIRD",
                    )
                )
        return predictions
    finally:
        Path(path).unlink(missing_ok=True)


def classify_birdnet(audio_bytes: bytes) -> list[BirdnetPrediction]:
    if not audio_bytes:
        return []

    try:
        return _analyze_with_birdnetlib(audio_bytes)
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("birdnetlib analysis failed: %s", exc)

    try:
        return _analyze_with_birdnet_analyzer(audio_bytes)
    except ImportError:
        return []
    except Exception as exc:
        logger.debug("birdnet_analyzer analysis failed: %s", exc)
        return []
