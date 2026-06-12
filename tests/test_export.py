from starscream.export.records import recording_to_row
from starscream.export.split import assign_split


def test_assign_split_deterministic():
    assert assign_split("DE") == assign_split("DE")
    assert assign_split("taxonomy.WILDLIFE.BIRD") in ("train", "val")


def test_recording_to_row_minimal():
    class FakeRecording:
        id = "00000000-0000-0000-0000-000000000001"
        title = "Test"
        description = None
        source_object = "door"
        source_action = "closing"
        taxonomy_code = "URBAN"
        tags = ["door"]
        material = "wood"
        environment = "indoor"
        location_name = "NYC"
        country_code = "US"
        altitude_m = None
        recorded_at = __import__("datetime").datetime(2024, 1, 1, tzinfo=__import__("datetime").timezone.utc)
        season = None
        habitat = None
        license = type("L", (), {"value": "CC0"})()
        duration_s = 1.0
        sample_rate_hz = 48000
        channels = 1
        bit_depth = 16
        recorder_type = type("R", (), {"value": "smartphone"})()
        recorder_model = None
        contributor_id = None
        contributor_name = None
        spectral_hash = "abc"
        is_contribution = True
        world_model_labels = {"object_category": "furniture", "interaction_type": "impact"}
        flac_key = "flac/abc.flac"
        mp3_key = None
        external_id = "fs-999"
        external_url = "https://freesound.org/people/x/sounds/999/"
        source = type("S", (), {"slug": "freesound"})()

    row = recording_to_row(FakeRecording(), 40.0, -73.0, "audio/x.flac", "train")
    assert row["source_object"] == "door"
    assert row["wm_object_category"] == "furniture"
    assert row["split"] == "train"
    assert row["lat"] == 40.0
    assert row["has_audio"] is True
    assert row["external_id"] == "fs-999"
    assert row["external_url"] == "https://freesound.org/people/x/sounds/999/"
    assert row["source_slug"] == "freesound"


def test_recording_to_row_pointer_only():
    class PointerRecording:
        id = "00000000-0000-0000-0000-000000000002"
        title = "Vintage broadcast"
        description = None
        source_object = "radio"
        source_action = "speaking"
        taxonomy_code = "HUMAN"
        tags = []
        material = None
        environment = None
        location_name = None
        country_code = None
        altitude_m = None
        recorded_at = __import__("datetime").datetime(2024, 1, 1, tzinfo=__import__("datetime").timezone.utc)
        season = None
        habitat = None
        license = type("L", (), {"value": "POINTER_ONLY"})()
        duration_s = None
        sample_rate_hz = None
        channels = None
        bit_depth = None
        recorder_type = type("R", (), {"value": "unknown"})()
        recorder_model = None
        contributor_id = None
        contributor_name = None
        spectral_hash = "ptr"
        is_contribution = False
        world_model_labels = {"object_category": "human", "interaction_type": "speaking"}
        flac_key = None
        mp3_key = None
        external_id = "ia-abc"
        external_url = "https://archive.org/details/abc"
        source = type("S", (), {"slug": "internet-archive"})()
        cross_modal_links = None
        events = None
        scene_graph = None

    row = recording_to_row(PointerRecording(), 0.0, 0.0, None, "val")
    assert row["has_audio"] is False
    assert row["audio"] is None
    assert row["source_slug"] == "internet-archive"
