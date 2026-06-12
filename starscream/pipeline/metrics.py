"""Lightweight in-process counters for pipeline failure visibility."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PipelineMetrics:
    enrichment_geocode_failures: int = 0
    enrichment_habitat_failures: int = 0
    enrichment_weather_failures: int = 0
    enrichment_osm_failures: int = 0
    index_failures: int = 0
    fingerprint_fallbacks: int = 0


_lock = threading.Lock()
_metrics = PipelineMetrics()


def get_metrics() -> PipelineMetrics:
    with _lock:
        return PipelineMetrics(**_metrics.__dict__)


def record_enrichment_failure(step: str, exc: Exception) -> None:
    with _lock:
        attr = f"enrichment_{step}_failures"
        if hasattr(_metrics, attr):
            setattr(_metrics, attr, getattr(_metrics, attr) + 1)
    logger.warning("Enrichment step %s failed: %s", step, exc)


def record_index_failure(recording_id: str, exc: Exception) -> None:
    with _lock:
        _metrics.index_failures += 1
    logger.warning("Index failure for %s: %s", recording_id, exc)


def record_fingerprint_fallback(exc: Exception) -> None:
    with _lock:
        _metrics.fingerprint_fallbacks += 1
    logger.debug("Fingerprint fallback hash used: %s", exc)
