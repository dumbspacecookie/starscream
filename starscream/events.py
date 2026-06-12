"""In-memory ingest event broadcaster for development.

Production deployments should replace this with Redis pub/sub so events
propagate across multiple API workers. See docs/DEPLOY.md.
"""

from __future__ import annotations

import math
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from starscream.db.models import Recording


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass(frozen=True)
class StreamFilter:
    taxonomy_prefix: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_km: float | None = None

    def matches(self, summary: dict[str, Any]) -> bool:
        if self.taxonomy_prefix:
            code = summary.get("taxonomy_code", "")
            if not str(code).startswith(self.taxonomy_prefix):
                return False

        if self.lat is not None and self.lng is not None and self.radius_km is not None:
            location = summary.get("location") or {}
            event_lat = location.get("lat")
            event_lng = location.get("lng")
            if event_lat is None or event_lng is None:
                return False
            if _haversine_km(self.lat, self.lng, float(event_lat), float(event_lng)) > self.radius_km:
                return False

        return True

    def as_dict(self) -> dict[str, Any]:
        return {
            "taxonomy_prefix": self.taxonomy_prefix,
            "lat": self.lat,
            "lng": self.lng,
            "radius_km": self.radius_km,
        }


def recording_summary_from_recording(recording: Recording, lat: float, lng: float) -> dict[str, Any]:
    license = recording.license
    license_value = license.value if hasattr(license, "value") else str(license)

    return {
        "id": str(recording.id),
        "taxonomy_code": recording.taxonomy_code,
        "location": {"lat": lat, "lng": lng},
        "recorded_at": recording.recorded_at.isoformat(),
        "title": recording.title,
        "source_id": str(recording.source_id),
        "license": license_value,
        "is_contribution": recording.is_contribution,
        "is_duplicate": recording.is_duplicate,
        "duration_s": recording.duration_s,
        "location_name": recording.location_name,
        "country_code": recording.country_code,
    }


Callback = Callable[[dict[str, Any]], None]


class IngestBroadcaster:
    """Thread-safe in-memory pub/sub for ingest events (single-process dev)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, tuple[StreamFilter, Callback]] = {}

    def subscribe(self, stream_filter: StreamFilter, callback: Callback) -> str:
        sub_id = uuid.uuid4().hex
        with self._lock:
            self._subscribers[sub_id] = (stream_filter, callback)
        return sub_id

    def unsubscribe(self, sub_id: str) -> None:
        with self._lock:
            self._subscribers.pop(sub_id, None)

    def publish(self, recording_summary: dict[str, Any]) -> None:
        with self._lock:
            subscribers = list(self._subscribers.items())
        for _, (stream_filter, callback) in subscribers:
            if stream_filter.matches(recording_summary):
                callback(recording_summary)

    def reset(self) -> None:
        with self._lock:
            self._subscribers.clear()


_broadcaster: IngestBroadcaster | None = None


def get_broadcaster() -> IngestBroadcaster:
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = IngestBroadcaster()
    return _broadcaster
