import logging
import uuid

import meilisearch

from starscream.config import get_settings
from starscream.db.models import Recording
from starscream.pipeline.metrics import record_index_failure

logger = logging.getLogger(__name__)

INDEX_NAME = "recordings"


def _client() -> meilisearch.Client | None:
    settings = get_settings()
    try:
        return meilisearch.Client(settings.meilisearch_url, settings.meilisearch_api_key or None)
    except Exception as exc:
        logger.warning("Meilisearch unavailable: %s", exc)
        return None


def ensure_index() -> None:
    client = _client()
    if not client:
        return
    try:
        client.create_index(INDEX_NAME, {"primaryKey": "id"})
        client.index(INDEX_NAME).update_searchable_attributes(
            [
                "title",
                "source_object",
                "source_action",
                "description",
                "taxonomy_code",
                "location_name",
                "country_code",
                "habitat",
                "tags",
                "material",
            ]
        )
        client.index(INDEX_NAME).update_filterable_attributes(
            [
                "taxonomy_code",
                "country_code",
                "season",
                "habitat",
                "quality",
                "review_status",
                "material",
                "environment",
                "is_contribution",
                "tags",
            ]
        )
    except meilisearch.errors.MeilisearchApiError:
        pass


def index_recording(recording: Recording, lat: float, lng: float) -> None:
    client = _client()
    if not client:
        return
    doc = {
        "id": str(recording.id),
        "title": recording.title,
        "source_object": recording.source_object,
        "source_action": recording.source_action,
        "description": recording.description,
        "tags": recording.tags or [],
        "material": recording.material,
        "environment": recording.environment,
        "taxonomy_code": recording.taxonomy_code,
        "location_name": recording.location_name,
        "country_code": recording.country_code,
        "habitat": recording.habitat,
        "season": recording.season.value if recording.season else None,
        "quality": recording.quality,
        "review_status": recording.review_status.value,
        "is_contribution": recording.is_contribution,
        "recorded_at": recording.recorded_at.isoformat(),
        "lat": lat,
        "lng": lng,
    }
    try:
        client.index(INDEX_NAME).add_documents([doc])
    except Exception as exc:
        record_index_failure(str(recording.id), exc)


def remove_recording(recording_id: uuid.UUID) -> None:
    client = _client()
    if not client:
        return
    try:
        client.index(INDEX_NAME).delete_document(str(recording_id))
    except Exception as exc:
        logger.warning("Failed to remove recording %s from index: %s", recording_id, exc)
