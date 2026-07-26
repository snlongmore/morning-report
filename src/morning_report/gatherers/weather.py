"""Weather gatherer via Open-Meteo (keyless, free, no API key required)."""

from __future__ import annotations

import logging
from typing import Any

import requests

from morning_report.gatherers.base import BaseGatherer

logger = logging.getLogger(__name__)

_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Well-known coordinates for configured locations
_KNOWN_COORDS = {
    "west kirby, uk": (53.3726, -3.1836),
    "west kirby": (53.3726, -3.1836),
    "liverpool, uk": (53.4084, -2.9916),
    "london, uk": (51.5074, -0.1278),
}

# Map WMO weather codes to the English descriptions understood by the
# `weather_fr` filter in report/generator.py. Keeping the descriptions in the
# same vocabulary means the French translation layer needs no changes.
_WMO_DESC = {
    0: "clear sky",
    1: "few clouds",
    2: "scattered clouds",
    3: "overcast clouds",
    45: "fog",
    48: "fog",
    51: "light intensity drizzle",
    53: "drizzle",
    55: "drizzle",
    56: "drizzle",
    57: "drizzle",
    61: "light rain",
    63: "moderate rain",
    65: "heavy intensity rain",
    66: "rain",
    67: "rain",
    71: "light snow",
    73: "snow",
    75: "snow",
    77: "snow",
    80: "shower rain",
    81: "shower rain",
    82: "shower rain",
    85: "snow",
    86: "snow",
    95: "thunderstorm",
    96: "thunderstorm",
    99: "thunderstorm",
}


def _get_coords(location: str) -> tuple[float, float] | None:
    """Look up coordinates for a location name."""
    key = location.lower().strip()
    return _KNOWN_COORDS.get(key)


def _describe(code: Any) -> str:
    """Turn a WMO weather code into an English description string."""
    try:
        return _WMO_DESC.get(int(code), "")
    except (TypeError, ValueError):
        return ""


class WeatherGatherer(BaseGatherer):
    """Gathers weather data from Open-Meteo.

    Open-Meteo needs no API key, so this gatherer is always available. It
    resolves each configured location to coordinates via ``_KNOWN_COORDS`` and
    skips any it cannot place.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._locations = self._config.get("locations", ["West Kirby, UK"])

    @property
    def name(self) -> str:
        return "weather"

    def is_available(self) -> bool:
        return True

    def gather(self) -> dict[str, Any]:
        """Fetch current weather and a 24h forecast for configured locations."""
        forecasts: dict[str, Any] = {}

        for location in self._locations:
            coords = _get_coords(location)
            if coords is None:
                logger.warning("No known coordinates for %s, skipping", location)
                forecasts[location] = {"error": f"unknown location: {location}"}
                continue

            lat, lon = coords
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": (
                    "temperature_2m,apparent_temperature,"
                    "relative_humidity_2m,wind_speed_10m,weather_code"
                ),
                "hourly": "temperature_2m,weather_code",
                "wind_speed_unit": "ms",
                "timezone": "auto",
                "forecast_hours": 24,
            }

            try:
                resp = requests.get(_OPEN_METEO_URL, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning("Failed to fetch weather for %s: %s", location, e)
                forecasts[location] = {"error": str(e)}
                continue

            current = data.get("current", {})
            forecasts[location] = {
                "current": {
                    "description": _describe(current.get("weather_code")),
                    "temp": current.get("temperature_2m"),
                    "feels_like": current.get("apparent_temperature"),
                    "humidity": current.get("relative_humidity_2m"),
                    "wind_speed": current.get("wind_speed_10m"),
                },
            }

            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            temps = hourly.get("temperature_2m", [])
            codes = hourly.get("weather_code", [])
            # Every 3rd hour over the next 24h gives 8 entries, matching the
            # old 3-hourly forecast table.
            forecast_items = []
            for i in range(0, len(times), 3):
                forecast_items.append({
                    "time": times[i],
                    "description": _describe(codes[i] if i < len(codes) else None),
                    "temp": temps[i] if i < len(temps) else None,
                })
                if len(forecast_items) >= 8:
                    break
            forecasts[location]["forecast"] = forecast_items

        return {"locations": forecasts}
