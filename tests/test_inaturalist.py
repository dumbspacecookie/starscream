from starscream.federation.inaturalist import (
    map_license,
    map_taxonomy,
    parse_observation,
)


def test_map_license_cc_by():
    assert map_license("cc-by") == "CC-BY"
    assert map_license("CC0") == "CC0"


def test_map_license_nc():
    assert map_license("cc-by-nc") == "CC-BY-NC"


def test_map_taxonomy_bird():
    assert map_taxonomy({"iconic_taxon_name": "Aves"}) == "WILDLIFE.BIRD"


def test_parse_observation_minimal():
    obs = {
        "id": 99,
        "description": "Song at dawn",
        "place_guess": "Central Park, NY",
        "observed_on": "2024-06-15",
        "time_observed_at": "2024-06-15T06:30:00-04:00",
        "geojson": {"type": "Point", "coordinates": [-73.97, 40.78]},
        "taxon": {
            "name": "Turdus migratorius",
            "preferred_common_name": "American Robin",
            "iconic_taxon_name": "Aves",
        },
        "sounds": [
            {
                "id": 1,
                "license_code": "cc-by",
                "file_url": "https://static.inaturalist.org/sounds/1.mp3",
            }
        ],
        "user": {"login": "birder42"},
    }
    record = parse_observation(obs)
    assert record is not None
    assert record.external_id == "99"
    assert record.license == "CC-BY"
    assert record.source_object == "American Robin"
    assert record.taxonomy_code == "WILDLIFE.BIRD"
    assert record.lat == 40.78
    assert record.lng == -73.97
    assert record.preview_url.endswith(".mp3")


def test_parse_observation_accepts_nc_sound_as_pointer_only():
    obs = {
        "id": 1,
        "observed_on": "2024-06-15",
        "taxon": {"name": "Turdus migratorius", "iconic_taxon_name": "Aves"},
        "sounds": [{"license_code": "cc-by-nc", "file_url": "https://example.com/x.mp3"}],
    }
    record = parse_observation(obs)
    assert record is not None
    assert record.license == "CC-BY-NC"
