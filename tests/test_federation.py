from starscream.federation.freesound import map_license, map_taxonomy, parse_sound


def test_map_license_cc0():
    assert map_license("Creative Commons 0") == "CC0"


def test_map_license_by():
    assert map_license("Attribution") == "CC-BY"


def test_map_taxonomy_bird():
    assert map_taxonomy(["field-recording", "bird"], "Robin singing") == "WILDLIFE.BIRD"


def test_parse_sound_minimal():
    sound = {
        "id": 12345,
        "name": "Door slam",
        "description": "A door slamming shut",
        "tags": ["door", "slam", "indoor"],
        "license": "Attribution",
        "created": "2024-06-15T10:00:00",
        "username": "recorder1",
        "duration": 2.5,
        "geotag": "40.758 -73.985",
        "url": "https://freesound.org/sounds/12345/",
        "previews": {"preview-hq-mp3": "https://freesound.org/preview/12345.mp3"},
    }
    record = parse_sound(sound)
    assert record is not None
    assert record.external_id == "12345"
    assert record.license == "CC-BY"
    assert record.lat == 40.758
    assert record.lng == -73.985
    assert record.preview_url.endswith(".mp3")


def test_parse_sound_skips_unknown_license():
    sound = {
        "id": 1,
        "name": "x",
        "tags": [],
        "license": "Sampling+",
        "created": "2024-01-01T00:00:00",
    }
    assert parse_sound(sound) is None


def test_upload_page_served():
    from fastapi.testclient import TestClient

    from starscream.api.main import app

    client = TestClient(app)
    response = client.get("/upload")
    assert response.status_code == 200
    assert "Starscream" in response.text
    assert "source_object" in response.text
