"""Tests for French learning report generation."""

from datetime import datetime
from pathlib import Path

import pytest

from morning_report.report.generator import (
    generate_report,
    french_date,
    FRENCH_DAYS,
    FRENCH_MONTHS,
    WEATHER_FR,
    _weather_fr,
)


# -- Shared test data --------------------------------------------------------

SAMPLE_DATA = {
    "weather": {
        "status": "ok",
        "locations": {
            "West Kirby, UK": {
                "current": {
                    "description": "overcast clouds",
                    "temp": 10.2,
                    "feels_like": 8.5,
                    "humidity": 82,
                    "wind_speed": 5.1,
                },
            }
        },
    },
    "markets": {
        "status": "ok",
        "crypto": {
            "bitcoin": {"symbol": "BTC", "price_usd": 67943.50, "change_24h_pct": 2.3},
            "ethereum": {"symbol": "ETH", "price_usd": 2045.20, "change_24h_pct": -1.1},
        },
        "stocks": {},
    },
    "meditation": {
        "status": "ok",
        "items": [
            {
                "title": "The Power of Letting Go",
                "summary": "Today's meditation focuses on surrender.",
                "content": "Richard Rohr reflects on the practice of letting go.",
                "link": "http://cac.org/meditation",
                "published": "2026-02-26",
                "source": "Center for Action and Contemplation",
            },
        ],
    },
}

SAMPLE_FRENCH_CONTENT = {
    "meditation_fr": "Richard Rohr reflechit sur la pratique du lacher prise.",
    "poem": {
        "text": "La pluie tombe doucement\nSur les toits gris du matin",
        "author": "Anonyme",
    },
    "history": {
        "year": 1872,
        "text": "Le premier parc national, Yellowstone, a ete cree.",
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
        "rule": "Le passe compose avec avoir",
        "explanation": "Use avoir + past participle for most verbs.",
        "examples": ["J'ai reflechi", "Il a lache prise"],
    },
    "exercise": {
        "instruction": "Completez avec le mot correct :",
        "questions": ["La ___ tombe doucement.", "Le ___ est en hausse."],
        "answers": ["pluie", "marche"],
    },
}


# -- French date helpers -----------------------------------------------------

class TestFrenchDateHelpers:
    def test_french_days_complete(self):
        expected = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
        assert set(FRENCH_DAYS.keys()) == expected

    def test_french_months_complete(self):
        assert set(FRENCH_MONTHS.keys()) == set(range(1, 13))

    def test_french_date_formatting(self):
        dt = datetime(2026, 2, 26)  # Thursday
        result = french_date(dt)
        assert result == "jeudi 26 fevrier 2026"

    def test_french_date_january(self):
        dt = datetime(2026, 1, 1)  # Thursday
        result = french_date(dt)
        assert result == "jeudi 1 janvier 2026"

    def test_french_date_december(self):
        dt = datetime(2025, 12, 25)  # Thursday
        result = french_date(dt)
        assert result == "jeudi 25 decembre 2025"


# -- Report generation -------------------------------------------------------

class TestReportGeneration:
    def test_generates_french_report(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "Francais du jour" in report

    def test_report_filename(self, tmp_path):
        dt = datetime(2026, 2, 26)
        generate_report(SAMPLE_DATA, output_dir=tmp_path, date=dt,
                        french_content=SAMPLE_FRENCH_CONTENT)
        assert (tmp_path / "2026-02-26.md").exists()

    def test_has_french_date(self, tmp_path):
        dt = datetime(2026, 2, 26)
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path, date=dt,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "jeudi 26 fevrier 2026" in report

    def test_weather_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "Meteo" in report
        assert "humidite" in report
        assert "vent" in report

    def test_weather_translated(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "ciel couvert" in report.lower()

    def test_markets_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "Marches" in report
        assert "Jeton" in report
        assert "Variation 24h" in report

    def test_meditation_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "Meditation du jour" in report
        assert "The Power of Letting Go" in report

    def test_meditation_french_translation(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "lacher prise" in report

    def test_meditation_fallback_to_english(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content={})
        assert "Traduction indisponible" in report
        assert "letting go" in report

    def test_poem_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "Poeme du jour" in report
        assert "pluie tombe doucement" in report
        assert "Anonyme" in report

    def test_history_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "Ce jour dans l'histoire" in report
        assert "1872" in report
        assert "Yellowstone" in report

    def test_vocabulary_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "Vocabulaire" in report
        assert "la pluie" in report
        assert "rain" in report

    def test_expression_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "Expression du jour" in report
        assert "Apres la pluie" in report

    def test_grammar_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "Point de grammaire" in report
        assert "passe compose" in report

    def test_exercise_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "Exercice" in report
        assert "Completez" in report
        assert "Reponses" in report

    def test_report_ends_correctly(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "bonne journee" in report

    def test_no_placeholder_sections(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path,
                                 french_content=SAMPLE_FRENCH_CONTENT)
        assert "Section completee par le skill" not in report

    def test_empty_data_graceful(self, tmp_path):
        report = generate_report({}, output_dir=tmp_path, french_content={})
        assert "Francais du jour" in report
        assert "bonne journee" in report

    def test_no_french_content_still_renders(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path)
        assert "Francais du jour" in report
        assert "Meteo" in report


# -- Weather translation ---------------------------------------------------

class TestWeatherTranslation:
    def test_common_descriptions(self):
        assert _weather_fr("overcast clouds") == "ciel couvert"
        assert _weather_fr("light rain") == "pluie legere"
        assert _weather_fr("clear sky") == "ciel degage"
        assert _weather_fr("scattered clouds") == "nuages epars"

    def test_case_insensitive(self):
        assert _weather_fr("Overcast Clouds") == "ciel couvert"
        assert _weather_fr("LIGHT RAIN") == "pluie legere"

    def test_unknown_falls_back(self):
        assert _weather_fr("volcanic ash") == "volcanic ash"

    def test_weather_in_report(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path)
        assert "ciel couvert" in report.lower()
        assert "overcast clouds" not in report.lower()
