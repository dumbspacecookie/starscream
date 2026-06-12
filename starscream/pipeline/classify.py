"""ML classification pipeline — suggestions only, never overrides user taxonomy."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from starscream.db.models import RecordingClassification
from starscream.pipeline.classifiers.birdnet import MODEL_NAME as BIRDNET_MODEL
from starscream.pipeline.classifiers.birdnet import classify_birdnet
from starscream.pipeline.classifiers.yamnet import MODEL_NAME as YAMNET_MODEL
from starscream.pipeline.classifiers.yamnet import classify_yamnet


@dataclass(frozen=True)
class ClassificationSuggestion:
    model_name: str
    label: str
    confidence: float
    taxonomy_suggestion: str | None = None


@dataclass
class Classification:
    suggestions: list[ClassificationSuggestion]


def classify_audio(audio_bytes: bytes | None, fallback_taxonomy: str) -> Classification:
    """Run available classifiers and return ranked suggestions.

    User-provided ``fallback_taxonomy`` is context only — results never replace it.
    """
    del fallback_taxonomy  # reserved for future context-aware ranking

    if not audio_bytes:
        return Classification(suggestions=[])

    suggestions: list[ClassificationSuggestion] = []

    for pred in classify_yamnet(audio_bytes):
        suggestions.append(
            ClassificationSuggestion(
                model_name=YAMNET_MODEL,
                label=pred.label,
                confidence=pred.confidence,
                taxonomy_suggestion=pred.taxonomy_suggestion,
            )
        )

    for pred in classify_birdnet(audio_bytes):
        suggestions.append(
            ClassificationSuggestion(
                model_name=BIRDNET_MODEL,
                label=pred.label,
                confidence=pred.confidence,
                taxonomy_suggestion=pred.taxonomy_suggestion,
            )
        )

    suggestions.sort(key=lambda item: item.confidence, reverse=True)
    return Classification(suggestions=suggestions)


def persist_classifications(
    db: Session,
    recording_id: uuid.UUID,
    classification: Classification,
) -> None:
    """Store classifier suggestions for a recording."""
    for item in classification.suggestions:
        db.add(
            RecordingClassification(
                recording_id=recording_id,
                model_name=item.model_name,
                label=item.label,
                confidence=item.confidence,
                taxonomy_suggestion=item.taxonomy_suggestion,
            )
        )
