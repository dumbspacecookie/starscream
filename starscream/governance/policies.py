"""Canonical governance policy definitions for Starscream Foundation."""

from __future__ import annotations

from typing import Any

GOVERNANCE_SUMMARY: dict[str, Any] = {
    "license_policy": {
        "summary": "Contributed recordings must be CC0 or CC-BY only.",
        "allowed_licenses": ["CC0", "CC-BY"],
        "disallowed_terms": ["NC", "ND"],
        "federated_non_cc": "pointer_only",
        "documentation_url": "https://starscream.org/docs/GOVERNANCE.md",
    },
    "foundation": {
        "name": "Starscream Foundation",
        "type": "nonprofit",
        "board_election": {
            "frequency": "annual",
            "voter_weighting": "verified_contribution_volume",
            "principle": "No single organization controls the dataset.",
        },
    },
    "dispute_resolution": {
        "process": "wikipedia_style",
        "steps": ["flag", "discuss_on_talk_page", "escalate_to_arbitration_committee"],
        "vandalism_handling": "Automatic detection plus moderator council review.",
    },
    "mirror_reciprocity": {
        "threshold_tb": 10,
        "requirement": "Organizations mirroring more than 10 TB must provide a public seed.",
        "principle": "Infrastructure reciprocity for bulk mirrors.",
    },
    "ai_training_clause": {
        "required": True,
        "summary": "Models trained on Starscream data must publish a model card crediting the corpus.",
        "attribution": "Individual contributors via contributor_id fields in training metadata.",
        "tooling": "starscream-model-card generate",
        "documentation_url": "https://starscream.org/docs/MODEL_CARD.md",
    },
}


def get_governance_summary() -> dict[str, Any]:
    """Return a copy of the governance policy summary for API responses."""
    return dict(GOVERNANCE_SUMMARY)
