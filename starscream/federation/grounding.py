"""Heuristic world-model fields for federated / imported rows."""

from __future__ import annotations

# Verb-like tokens in tags/titles → source_action
_ACTION_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("bark", "barking", "dog"), "barking"),
    (("meow", "cat"), "meowing"),
    (("chirp", "tweet", "song", "vocal", "call", "bird", "birds"), "vocalizing"),
    (("rain", "rainfall", "drizzle"), "falling"),
    (("thunder", "storm"), "thundering"),
    (("traffic", "engine", "motor", "vehicle"), "operating"),
    (("door", "slam", "close", "closing"), "closing"),
    (("footstep", "walk", "walking"), "walking"),
    (("wind", "gust"), "gusting"),
    (("wave", "ocean", "surf"), "breaking"),
    (("fire", "burn", "crackle"), "burning"),
    (("click", "tick", "clock"), "ticking"),
    (("laugh", "speech", "talk", "crowd"), "speaking"),
    (("gun", "shot", "gunshot"), "firing"),
    (("siren", "alarm"), "sounding"),
)

# Normalize category labels to readable source_object nouns
_OBJECT_OVERRIDES = {
    "dog": "domestic dog",
    "cat": "domestic cat",
    "chirping_birds": "bird flock",
    "crow": "crow",
    "hen": "hen",
    "insects": "insects",
    "sheep": "sheep",
    "cow": "cow",
    "frog": "frog",
    "rain": "rainfall",
    "thunderstorm": "thunderstorm",
    "wind": "wind",
    "sea_waves": "ocean waves",
    "crackling_fire": "fire",
    "crickets": "crickets",
    "water_drops": "water droplets",
    "footsteps": "footsteps",
    "door_wood_knock": "wooden door",
    "car_horn": "vehicle horn",
    "engine": "engine",
    "train": "train",
    "airplane": "airplane",
    "siren": "emergency siren",
}


def _normalize_token(text: str) -> str:
    return text.strip().lower().replace("-", " ").replace("_", " ")


def infer_source_action(title: str | None, tags: list[str]) -> str:
    haystack = _normalize_token(" ".join([title or "", *tags]))
    for keywords, action in _ACTION_HINTS:
        if any(kw in haystack for kw in keywords):
            return action
    return "producing sound"


def infer_source_object(title: str | None, tags: list[str], *, category: str | None = None) -> str:
    if category:
        key = category.strip().lower()
        if key in _OBJECT_OVERRIDES:
            return _OBJECT_OVERRIDES[key]
        return key.replace("_", " ")

    if tags:
        return tags[0].replace("_", " ")

    if title:
        return title.strip()

    return "unknown sound source"


def ground_federated_fields(
    *,
    title: str | None,
    tags: list[str],
    category: str | None = None,
) -> tuple[str, str]:
    """Return (source_object, source_action) for federated/imported rows."""
    obj = infer_source_object(title, tags, category=category)
    action = infer_source_action(title, tags)
    return obj, action


_GENERIC_ACTIONS = frozenset(
    {
        "producing sound",
        "archived_recording",
        "recorded_event",
        "sound event",
        "vocalization",
    }
)

_WEAK_OBJECTS = frozenset({"unknown sound source", "unknown", ""})


def maybe_ground_record(
    source_object: str | None,
    source_action: str | None,
    *,
    title: str | None,
    tags: list[str],
    category: str | None = None,
) -> tuple[str, str]:
    """Fill weak connector fields using title/tag heuristics."""
    obj = (source_object or "").strip()
    action = (source_action or "").strip()
    weak_object = not obj or obj.lower() in _WEAK_OBJECTS
    weak_action = not action or action in _GENERIC_ACTIONS
    if weak_object or weak_action:
        inferred_obj, inferred_action = ground_federated_fields(
            title=title, tags=tags, category=category
        )
        if weak_object:
            obj = inferred_obj
        if weak_action:
            action = inferred_action
    return obj or "unknown sound source", action or "producing sound"


_TAXONOMY_TOP_CATEGORY = {
    "WILDLIFE": "organism",
    "ATMOSPHERIC": "environment",
    "NATURAL": "environment",
    "URBAN": "artifact",
    "MACHINERY": "machine",
    "HUMAN": "human",
    "bio": "organism",
    "env": "environment",
    "mach": "machine",
    "arch": "artifact",
}


def infer_minimal_world_model_labels(
    taxonomy_code: str,
    source_object: str,
    source_action: str,
) -> dict[str, str]:
    """Lightweight physical labels when enrichment/classifiers did not run."""
    top = taxonomy_code.split(".", 1)[0] if taxonomy_code else "unknown"
    return {
        "object_category": _TAXONOMY_TOP_CATEGORY.get(top, top.lower()),
        "interaction_type": source_action,
        "source_object": source_object,
    }
