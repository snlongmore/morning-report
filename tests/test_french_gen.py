"""Tests for French content generation via Anthropic API."""

import json
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from morning_report.french_gen import (
    generate_french_content,
    _build_system_prompt,
    _build_user_prompt,
    _extract_json,
    _weather_summary,
    _markets_summary,
    _meditation_text,
    _EXPECTED_KEYS,
    _FALLBACK_MSG,
)


# -- Sample data ---------------------------------------------------------------

WEATHER_DATA = {
    "status": "ok",
    "locations": {
        "West Kirby, UK": {
            "current": {
                "description": "light rain",
                "temp": 10.5,
                "feels_like": 8.2,
                "humidity": 85,
                "wind_speed": 4.5,
            },
        }
    },
}

MARKETS_DATA = {
    "status": "ok",
    "crypto": {
        "bitcoin": {"symbol": "BTC", "price_usd": 67000.00, "change_24h_pct": 1.5},
        "allora": {"symbol": "ALLO", "price_usd": 0.0234, "change_24h_pct": -3.2},
    },
}

MEDITATION_DATA = {
    "status": "ok",
    "items": [
        {
            "title": "The Power of Letting Go",
            "summary": "Today's meditation focuses on surrender.",
            "content": "Richard Rohr reflects on the practice of letting go.",
            "link": "http://cac.org/meditation",
        },
    ],
}

MOCK_API_RESPONSE = {
    "meditation_fr": "Richard Rohr reflechit sur la pratique du lacher prise.",
    "poem": {
        "text": "La pluie tombe doucement\nSur les toits gris du matin",
        "author": "Anonyme",
    },
    "history": {
        "year": 1872,
        "text": "Le premier parc national au monde, Yellowstone, a ete cree.",
    },
    "vocabulary": [
        {"fr": "la pluie", "en": "rain", "example": "La pluie tombe sur la ville."},
        {"fr": "le marche", "en": "market", "example": "Le marche est en hausse."},
    ],
    "expression": {
        "fr": "Apres la pluie, le beau temps",
        "en": "Every cloud has a silver lining",
        "example": "Ne t'inquiete pas, apres la pluie, le beau temps !",
    },
    "grammar": {
        "rule": "Le passe compose avec 'avoir'",
        "explanation": "For most verbs, use avoir + past participle.",
        "examples": ["J'ai reflechi", "Il a lache prise"],
    },
    "exercise": {
        "instruction": "Completez avec le mot correct :",
        "questions": ["La ___ tombe doucement.", "Le ___ est en hausse."],
        "answers": ["pluie", "marche"],
    },
}


# -- Helper function tests ----------------------------------------------------

class TestWeatherSummary:
    def test_ok_data(self):
        result = _weather_summary(WEATHER_DATA)
        assert "West Kirby" in result
        assert "light rain" in result
        assert "10.5" in result

    def test_error_status(self):
        assert _weather_summary({"status": "error"}) == "Weather data unavailable."

    def test_empty_locations(self):
        assert _weather_summary({"status": "ok", "locations": {}}) == "Weather data unavailable."


class TestMarketsSummary:
    def test_ok_data(self):
        result = _markets_summary(MARKETS_DATA)
        assert "BTC" in result
        assert "ALLO" in result

    def test_error_status(self):
        assert _markets_summary({"status": "error"}) == "Markets data unavailable."

    def test_formats_high_price(self):
        result = _markets_summary(MARKETS_DATA)
        assert "$67,000" in result

    def test_formats_low_price(self):
        result = _markets_summary(MARKETS_DATA)
        assert "$0.0234" in result


class TestMeditationText:
    def test_uses_content_over_summary(self):
        result = _meditation_text(MEDITATION_DATA)
        assert "letting go" in result

    def test_falls_back_to_summary(self):
        data = {
            "status": "ok",
            "items": [{"summary": "Summary text", "link": "http://example.com"}],
        }
        result = _meditation_text(data)
        assert result == "Summary text"

    def test_empty_items(self):
        result = _meditation_text({"status": "ok", "items": []})
        assert "No meditation" in result

    def test_error_status(self):
        result = _meditation_text({"status": "error"})
        assert "unavailable" in result


# -- JSON extraction -----------------------------------------------------------

class TestExtractJson:
    def test_direct_json(self):
        data = {"key": "value"}
        result = _extract_json(json.dumps(data))
        assert result == data

    def test_code_block_json(self):
        json_str = json.dumps({"key": "value"})
        wrapped = f"```json\n{json_str}\n```"
        result = _extract_json(wrapped)
        assert result == {"key": "value"}

    def test_fallback_raw_text(self):
        result = _extract_json("This is not JSON at all")
        assert result["meditation_fr"] == "This is not JSON at all"
        assert result.get("_parse_error") is True

    def test_whitespace_handling(self):
        result = _extract_json('  {"key": "value"}  ')
        assert result == {"key": "value"}


# -- Prompt building ----------------------------------------------------------

class TestBuildPrompts:
    def test_system_prompt_includes_level(self):
        prompt = _build_system_prompt("B1")
        assert "B1" in prompt
        assert "JSON" in prompt

    def test_user_prompt_includes_data(self):
        prompt = _build_user_prompt(
            date=datetime(2026, 3, 1),
            weather_summary="West Kirby: light rain, 10°C",
            markets_summary="BTC $67,000",
            meditation_text="Test meditation text.",
        )
        assert "West Kirby" in prompt
        assert "BTC" in prompt
        assert "Test meditation text" in prompt
        assert "meditation_fr" in prompt
        assert "poem" in prompt
        assert "vocabulary" in prompt


# -- Main generation function -------------------------------------------------

class TestGenerateFrenchContent:
    def _make_mock_response(self, content_dict):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = json.dumps(content_dict)
        mock_response.content = [mock_block]
        return mock_response

    def _make_mock_anthropic(self, mock_client=None):
        """Create a mock anthropic module with a working Anthropic class."""
        mock_mod = MagicMock()
        if mock_client:
            mock_mod.Anthropic.return_value = mock_client
        mock_mod.AuthenticationError = type("AuthenticationError", (Exception,), {})
        return mock_mod

    def test_successful_generation(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = self._make_mock_response(MOCK_API_RESPONSE)
        mock_mod = self._make_mock_anthropic(mock_client)

        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                api_key="test-key",
                date=datetime(2026, 3, 1),
            )

        assert result["meditation_fr"] == MOCK_API_RESPONSE["meditation_fr"]
        assert result["poem"] == MOCK_API_RESPONSE["poem"]
        assert "_error" not in result

    def test_missing_keys_get_fallback(self):
        partial_response = {"meditation_fr": "Translated text."}
        mock_client = MagicMock()
        mock_client.messages.create.return_value = self._make_mock_response(partial_response)
        mock_mod = self._make_mock_anthropic(mock_client)

        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                api_key="test-key",
            )

        assert result["meditation_fr"] == "Translated text."
        for key in ("poem", "history", "vocabulary", "expression", "grammar", "exercise"):
            assert result[key] == _FALLBACK_MSG

    def test_api_call_failure(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API timeout")
        mock_mod = self._make_mock_anthropic(mock_client)

        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                api_key="test-key",
            )

        assert "_error" in result
        assert "API timeout" in result["_error"]
        for key in _EXPECTED_KEYS:
            assert result[key] == _FALLBACK_MSG

    def test_anthropic_not_installed(self):
        # Temporarily remove anthropic from sys.modules if present
        import sys
        saved = sys.modules.pop("anthropic", None)
        try:
            with patch.dict("sys.modules", {"anthropic": None}):
                result = generate_french_content(
                    WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                )
        finally:
            if saved is not None:
                sys.modules["anthropic"] = saved

        assert "_error" in result
        assert "not installed" in result["_error"]

    def test_custom_model(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = self._make_mock_response(MOCK_API_RESPONSE)
        mock_mod = self._make_mock_anthropic(mock_client)

        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                api_key="test-key",
                model="claude-sonnet-4-5-20250514",
            )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-5-20250514"

    def test_uses_configured_level(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = self._make_mock_response(MOCK_API_RESPONSE)
        mock_mod = self._make_mock_anthropic(mock_client)

        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                level="A2",
                api_key="test-key",
            )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "A2" in call_kwargs["system"]

    def test_auth_error_handling(self):
        mock_mod = MagicMock()
        mock_mod.AuthenticationError = type("AuthenticationError", (Exception,), {})
        mock_mod.Anthropic.side_effect = mock_mod.AuthenticationError("Invalid key")

        with patch.dict("sys.modules", {"anthropic": mock_mod}):
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                api_key="bad-key",
            )

        assert "_error" in result
        assert "API key" in result["_error"]
