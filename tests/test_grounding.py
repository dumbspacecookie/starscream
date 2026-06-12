"""Federated grounding heuristics."""

from starscream.federation.grounding import (
    ground_federated_fields,
    infer_minimal_world_model_labels,
    infer_source_action,
    maybe_ground_record,
)


def test_ground_dog_bark():
    obj, action = ground_federated_fields(title="Dog", tags=["dog", "bark"])
    assert obj == "dog"
    assert action == "barking"


def test_ground_esc50_category():
    obj, action = ground_federated_fields(
        title="rain",
        tags=["rain"],
        category="rain",
    )
    assert obj == "rainfall"
    assert action == "falling"


def test_infer_source_action_default():
    assert infer_source_action("ambient hum", []) == "producing sound"


def test_maybe_ground_weak_archive_fields():
    obj, action = maybe_ground_record(
        "Old Radio Show",
        "archived_recording",
        title="Rain on tin roof",
        tags=["rain", "storm"],
    )
    assert obj == "Old Radio Show"
    assert action == "falling"


def test_infer_minimal_world_model_labels():
    wm = infer_minimal_world_model_labels("WILDLIFE.BIRD", "american robin", "vocalizing")
    assert wm["object_category"] == "organism"
    assert wm["interaction_type"] == "vocalizing"
    assert wm["source_object"] == "american robin"


def test_infer_minimal_world_model_labels_atmospheric():
    wm = infer_minimal_world_model_labels("ATMOSPHERIC.RAIN", "rainfall", "falling")
    assert wm["object_category"] == "environment"
