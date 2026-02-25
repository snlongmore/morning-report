"""Tests for the Weather gatherer."""

from unittest.mock import patch, MagicMock

import pytest

from morning_report.gatherers.weather import WeatherGatherer, _get_coords


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


class TestWeatherGatherer:
    def test_name(self):
        g = WeatherGatherer()
        assert g.name == "weather"

    def test_not_available_without_key(self):
        g = WeatherGatherer(config={"api_key": ""})
        assert not g.is_available()

    def test_not_available_env_placeholder(self):
        g = WeatherGatherer(config={"api_key": "${OPENWEATHER_API_KEY}"})
        assert not g.is_available()

    def test_available_with_key(self):
        g = WeatherGatherer(config={"api_key": "real-key-123"})
        assert g.is_available()

    def test_gather_current_weather(self):
        mock_current = MagicMock()
        mock_current.json.return_value = {
            "weather": [{"description": "scattered clouds"}],
            "main": {"temp": 12.5, "feels_like": 10.2, "humidity": 78},
            "wind": {"speed": 5.4},
        }
        mock_current.raise_for_status = MagicMock()

        mock_forecast = MagicMock()
        mock_forecast.json.return_value = {
            "list": [
                {
                    "dt_txt": "2026-02-25 12:00:00",
                    "weather": [{"description": "light rain"}],
                    "main": {"temp": 11.0},
                },
                {
                    "dt_txt": "2026-02-25 15:00:00",
                    "weather": [{"description": "overcast clouds"}],
                    "main": {"temp": 10.5},
                },
            ],
        }
        mock_forecast.raise_for_status = MagicMock()

        def mock_get(url, **kwargs):
            if "forecast" in url:
                return mock_forecast
            return mock_current

        with patch("morning_report.gatherers.weather.requests.get", side_effect=mock_get):
            g = WeatherGatherer(config={
                "api_key": "test-key",
                "locations": ["West Kirby, UK"],
            })
            result = g.gather()

        loc = result["locations"]["West Kirby, UK"]
        assert loc["current"]["description"] == "scattered clouds"
        assert loc["current"]["temp"] == 12.5
        assert loc["current"]["humidity"] == 78
        assert len(loc["forecast"]) == 2
        assert loc["forecast"][0]["description"] == "light rain"

    def test_gather_always_uses_q_param(self):
        """Free-tier OWM doesn't support lat/lon — always use q= for location."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "weather": [{"description": "clear"}],
            "main": {"temp": 15, "feels_like": 14, "humidity": 60},
            "wind": {"speed": 3},
        }
        mock_resp.raise_for_status = MagicMock()

        mock_forecast = MagicMock()
        mock_forecast.json.return_value = {"list": []}
        mock_forecast.raise_for_status = MagicMock()

        calls = []

        def mock_get(url, **kwargs):
            calls.append(kwargs.get("params", {}))
            if "forecast" in url:
                return mock_forecast
            return mock_resp

        with patch("morning_report.gatherers.weather.requests.get", side_effect=mock_get):
            g = WeatherGatherer(config={
                "api_key": "test-key",
                "locations": ["West Kirby, UK"],
            })
            g.gather()

        assert "q" in calls[0]
        assert calls[0]["q"] == "West Kirby, UK"
        assert "lat" not in calls[0]

    def test_safe_gather_skipped_without_key(self):
        g = WeatherGatherer(config={"api_key": ""})
        result = g.safe_gather()
        assert result["status"] == "skipped"

    def test_gather_handles_api_error_per_location(self):
        """When API fails for a location, that location gets an error dict but gather still succeeds."""
        with patch("morning_report.gatherers.weather.requests.get", side_effect=Exception("timeout")):
            g = WeatherGatherer(config={
                "api_key": "test-key",
                "locations": ["West Kirby, UK"],
            })
            result = g.gather()

        assert "error" in result["locations"]["West Kirby, UK"]
