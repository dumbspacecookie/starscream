from datetime import datetime, timezone
from unittest.mock import patch

import httpx

from starscream.config import Settings
from starscream.db.models import Season
from starscream.pipeline.enrich import _derive_season, enrich_metadata
from starscream.pipeline.geocode import GeocodeResult, reverse_geocode
from starscream.pipeline.habitat import lookup_habitat
from starscream.pipeline.weather import WeatherResult, lookup_weather


NOMINATIM_RESPONSE = {
    "display_name": "Central Park, New York, United States",
    "address": {"country_code": "us", "city": "New York", "country": "United States"},
}

OPEN_METEO_RESPONSE = {
    "hourly": {
        "time": ["2024-07-15T14:00", "2024-07-15T15:00"],
        "temperature_2m": [28.5, 29.1],
        "weather_code": [2, 3],
    }
}


def _settings(**overrides) -> Settings:
    return Settings(
        enrich_geocode=overrides.pop("enrich_geocode", True),
        enrich_habitat=overrides.pop("enrich_habitat", True),
        enrich_weather=overrides.pop("enrich_weather", True),
        enrich_osm=overrides.pop("enrich_osm", False),
        **overrides,
    )


def test_derive_season_northern_summer():
    recorded = datetime(2024, 7, 15, tzinfo=timezone.utc)
    assert _derive_season(recorded, 45.0) == Season.SUMMER


def test_derive_season_southern_summer():
    recorded = datetime(2024, 1, 15, tzinfo=timezone.utc)
    assert _derive_season(recorded, -45.0) == Season.SUMMER


def test_lookup_habitat_amazon():
    assert lookup_habitat(-3.0, -60.0) == "tropical_rainforest"


def test_lookup_habitat_boreal():
    assert lookup_habitat(62.0, 25.0) == "boreal_forest"


def test_lookup_habitat_polar():
    assert lookup_habitat(70.0, 0.0) == "polar_tundra"


@patch("starscream.pipeline.geocode.httpx.get")
def test_reverse_geocode_success(mock_get):
    mock_response = mock_get.return_value
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = NOMINATIM_RESPONSE

    result = reverse_geocode(40.78, -73.97, user_agent="test-agent", rate_limit_s=0)

    assert result == GeocodeResult(
        location_name="Central Park, New York, United States",
        country_code="US",
    )
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs["headers"]["User-Agent"] == "test-agent"


@patch("starscream.pipeline.geocode.httpx.get")
def test_reverse_geocode_failure(mock_get):
    mock_get.side_effect = httpx.TimeoutException("timeout")

    result = reverse_geocode(0.0, 0.0, user_agent="test-agent", rate_limit_s=0)

    assert result == GeocodeResult(location_name=None, country_code=None)


@patch("starscream.pipeline.weather.httpx.get")
def test_lookup_weather_success(mock_get):
    mock_response = mock_get.return_value
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = OPEN_METEO_RESPONSE

    recorded = datetime(2024, 7, 15, 14, 30, tzinfo=timezone.utc)
    result = lookup_weather(40.78, -73.97, recorded)

    assert result == WeatherResult(weather="partly cloudy", temperature_c=28.5)


@patch("starscream.pipeline.weather.httpx.get")
def test_lookup_weather_failure(mock_get):
    mock_get.side_effect = httpx.HTTPStatusError(
        "error", request=httpx.Request("GET", "http://test"), response=httpx.Response(500)
    )

    recorded = datetime(2024, 7, 15, tzinfo=timezone.utc)
    result = lookup_weather(0.0, 0.0, recorded)

    assert result == WeatherResult(weather=None, temperature_c=None)


@patch("starscream.pipeline.enrich.lookup_weather")
@patch("starscream.pipeline.enrich.lookup_habitat")
@patch("starscream.pipeline.enrich.reverse_geocode")
def test_enrich_metadata_full(mock_geocode, mock_habitat, mock_weather):
    mock_geocode.return_value = GeocodeResult(
        location_name="Central Park, New York, United States",
        country_code="US",
    )
    mock_habitat.return_value = "temperate_forest"
    mock_weather.return_value = WeatherResult(weather="partly cloudy", temperature_c=28.5)

    recorded = datetime(2024, 7, 15, 14, tzinfo=timezone.utc)
    result = enrich_metadata(
        lat=40.78,
        lng=-73.97,
        recorded_at=recorded,
        location_name=None,
        country_code=None,
        settings=_settings(),
    )

    assert result.season == Season.SUMMER
    assert result.location_name == "Central Park, New York, United States"
    assert result.country_code == "US"
    assert result.habitat == "temperate_forest"
    assert result.weather == "partly cloudy"
    assert result.temperature_c == 28.5
    mock_geocode.assert_called_once()


@patch("starscream.pipeline.enrich.lookup_weather")
@patch("starscream.pipeline.enrich.lookup_habitat")
@patch("starscream.pipeline.enrich.reverse_geocode")
def test_enrich_metadata_preserves_provided_location(mock_geocode, mock_habitat, mock_weather):
    mock_habitat.return_value = "temperate_forest"
    mock_weather.return_value = WeatherResult(weather="clear", temperature_c=22.0)

    recorded = datetime(2024, 7, 15, tzinfo=timezone.utc)
    result = enrich_metadata(
        lat=40.78,
        lng=-73.97,
        recorded_at=recorded,
        location_name="My Spot",
        country_code="US",
        settings=_settings(),
    )

    mock_geocode.assert_not_called()
    assert result.location_name == "My Spot"
    assert result.country_code == "US"


@patch("starscream.pipeline.enrich.lookup_weather")
@patch("starscream.pipeline.enrich.lookup_habitat")
@patch("starscream.pipeline.enrich.reverse_geocode")
def test_enrich_metadata_toggles_off(mock_geocode, mock_habitat, mock_weather):
    recorded = datetime(2024, 7, 15, tzinfo=timezone.utc)
    result = enrich_metadata(
        lat=40.78,
        lng=-73.97,
        recorded_at=recorded,
        location_name="Existing",
        country_code="US",
        settings=_settings(enrich_geocode=False, enrich_habitat=False, enrich_weather=False),
    )

    mock_geocode.assert_not_called()
    mock_habitat.assert_not_called()
    mock_weather.assert_not_called()
    assert result.habitat is None
    assert result.weather is None
    assert result.temperature_c is None
    assert result.season == Season.SUMMER
