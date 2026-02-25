"""Weather gatherer via OpenWeatherMap API."""

from __future__ import annotations

import logging
from typing import Any

import requests

from morning_report.gatherers.base import BaseGatherer

logger = logging.getLogger(__name__)

_OWM_BASE = "https://api.openweathermap.org/data/2.5"

# Well-known coordinates for configured locations
_KNOWN_COORDS = {
    "west kirby, uk": (53.3726, -3.1836),
    "west kirby": (53.3726, -3.1836),
    "liverpool, uk": (53.4084, -2.9916),
    "london, uk": (51.5074, -0.1278),
}


def _get_coords(location: str) -> tuple[float, float] | None:
    """Look up coordinates for a location name."""
    key = location.lower().strip()
    return _KNOWN_COORDS.get(key)


class WeatherGatherer(BaseGatherer):
    """Gathers weather data from OpenWeatherMap."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._api_key = self._config.get("api_key", "")
        self._locations = self._config.get("locations", ["West Kirby, UK"])

    @property
    def name(self) -> str:
        return "weather"

    def is_available(self) -> bool:
        key = self._api_key
        if key.startswith("${"):
            return False
        return bool(key)

    def gather(self) -> dict[str, Any]:
        """Fetch current weather and forecast for configured locations."""
        forecasts: dict[str, Any] = {}

        for location in self._locations:
            coords = _get_coords(location)

            params: dict[str, Any] = {
                "appid": self._api_key,
                "units": "metric",
            }
            if coords:
                params["lat"] = coords[0]
                params["lon"] = coords[1]
            else:
                params["q"] = location

            # Current weather
            try:
                resp = requests.get(
                    f"{_OWM_BASE}/weather",
                    params=params,
                    timeout=10,
                )
                resp.raise_for_status()
                current = resp.json()

                weather_desc = current["weather"][0]["description"] if current.get("weather") else ""
                main = current.get("main", {})

                forecasts[location] = {
                    "current": {
                        "description": weather_desc,
                        "temp": main.get("temp"),
                        "feels_like": main.get("feels_like"),
                        "humidity": main.get("humidity"),
                        "wind_speed": current.get("wind", {}).get("speed"),
                    },
                }
            except Exception as e:
                logger.warning("Failed to fetch weather for %s: %s", location, e)
                forecasts[location] = {"error": str(e)}
                continue

            # 3-hour forecast (next 24h = 8 entries)
            try:
                resp = requests.get(
                    f"{_OWM_BASE}/forecast",
                    params=params,
                    timeout=10,
                )
                resp.raise_for_status()
                forecast_data = resp.json()

                forecast_items = []
                for item in forecast_data.get("list", [])[:8]:
                    weather_desc = item["weather"][0]["description"] if item.get("weather") else ""
                    forecast_items.append({
                        "time": item.get("dt_txt", ""),
                        "description": weather_desc,
                        "temp": item.get("main", {}).get("temp"),
                    })

                forecasts[location]["forecast"] = forecast_items

            except Exception as e:
                logger.warning("Failed to fetch forecast for %s: %s", location, e)

        return {"locations": forecasts}
