"""Tests for the Weather gatherer (Open-Meteo backend)."""

from unittest.mock import patch, MagicMock

from morning_report.gatherers.weather import WeatherGatherer, _get_coords, _describe


class TestGetCoords:
    def test_known_location(self):
        coords = _get_coords("West Kirby, UK")
        assert coords == (53.3726, -3.1836)

    def test_case_insensitive(self):
        coords = _get_coords("WEST KIRBY, UK")
        assert coords == (53.3726, -3.1836)

    def test_unknown_location(self):
        coords = _get_coords("Unknown City, Mars")
        assert coords is None


class TestDescribe:
    def test_known_code_maps_to_english(self):
        # These strings must remain keys in report.generator.WEATHER_FR.
        assert _describe(0) == "clear sky"
        assert _describe(61) == "light rain"
        assert _describe(95) == "thunderstorm"

    def test_unknown_code(self):
        assert _describe(12345) == ""

    def test_none_code(self):
        assert _describe(None) == ""


class TestWeatherGatherer:
    def test_name(self):
        g = WeatherGatherer()
        assert g.name == "weather"

    def test_always_available_no_key_needed(self):
        # Open-Meteo needs no API key, so the gatherer is always available.
        assert WeatherGatherer().is_available()
        assert WeatherGatherer(config={}).is_available()

    def test_gather_current_and_forecast(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "current": {
                "temperature_2m": 12.5,
                "apparent_temperature": 10.2,
                "relative_humidity_2m": 78,
                "wind_speed_10m": 5.4,
                "weather_code": 2,
            },
            "hourly": {
                "time": [f"2026-07-19T{h:02d}:00" for h in range(24)],
                "temperature_2m": [11.0 + i * 0.1 for i in range(24)],
                "weather_code": [61] * 24,
            },
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("morning_report.gatherers.weather.requests.get", return_value=mock_resp):
            g = WeatherGatherer(config={"locations": ["West Kirby, UK"]})
            result = g.gather()

        loc = result["locations"]["West Kirby, UK"]
        assert loc["current"]["description"] == "scattered clouds"
        assert loc["current"]["temp"] == 12.5
        assert loc["current"]["feels_like"] == 10.2
        assert loc["current"]["humidity"] == 78
        assert loc["current"]["wind_speed"] == 5.4
        # 24 hourly entries, every 3rd, capped at 8.
        assert len(loc["forecast"]) == 8
        assert loc["forecast"][0]["description"] == "light rain"
        assert loc["forecast"][0]["time"] == "2026-07-19T00:00"

    def test_gather_requests_coordinates_not_query(self):
        """Open-Meteo is coordinate-based — verify lat/lon are sent."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"current": {}, "hourly": {}}
        mock_resp.raise_for_status = MagicMock()

        calls = []

        def mock_get(url, **kwargs):
            calls.append(kwargs.get("params", {}))
            return mock_resp

        with patch("morning_report.gatherers.weather.requests.get", side_effect=mock_get):
            g = WeatherGatherer(config={"locations": ["West Kirby, UK"]})
            g.gather()

        assert calls[0]["latitude"] == 53.3726
        assert calls[0]["longitude"] == -3.1836
        assert "q" not in calls[0]

    def test_gather_skips_unknown_location(self):
        g = WeatherGatherer(config={"locations": ["Nowhere, Mars"]})
        result = g.gather()
        assert "error" in result["locations"]["Nowhere, Mars"]

    def test_gather_handles_api_error_per_location(self):
        with patch(
            "morning_report.gatherers.weather.requests.get",
            side_effect=Exception("timeout"),
        ):
            g = WeatherGatherer(config={"locations": ["West Kirby, UK"]})
            result = g.gather()

        assert "error" in result["locations"]["West Kirby, UK"]
