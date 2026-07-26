"""Tests for French content generation via Claude Code CLI."""

import json
import subprocess
from datetime import datetime
from unittest.mock import patch, MagicMock, call

import pytest

from morning_report.french_gen import (
    generate_french_content,
    _build_cli_env,
    _build_system_prompt,
    _build_user_prompt,
    _cli_error_message,
    _extract_json,
    _is_auth_error,
    _weather_summary,
    _markets_summary,
    _meditation_text,
    _EXPECTED_KEYS,
    _FALLBACK_MSG,
    _MAX_RETRIES,
)


@pytest.fixture(autouse=True)
def stub_claude_token():
    """Keep the Keychain out of every test in this module.

    Patching ``morning_report.french_gen.subprocess.run`` patches ``run`` on the
    shared ``subprocess`` module, so without this the Keychain lookup inside
    ``_build_cli_env`` would consume the ``side_effect`` entries that the CLI
    calls are meant to receive.
    """
    with patch("morning_report.french_gen.keychain.get_claude_token", return_value="tok-test"):
        yield


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
        assert "vocabulary" in prompt

    def test_user_prompt_without_poem(self):
        prompt = _build_user_prompt(
            date=datetime(2026, 3, 1),
            weather_summary="sunny",
            markets_summary="BTC $67,000",
            meditation_text="Test.",
        )
        assert "real French poem excerpt" not in prompt

    def test_user_prompt_with_poem(self):
        poem = {
            "title": "Demain, des l'aube",
            "author": "Victor Hugo",
            "source": "Les Contemplations (1856)",
            "excerpt": "Demain, des l'aube, a l'heure ou blanchit la campagne,",
            "themes": ["nature"],
        }
        prompt = _build_user_prompt(
            date=datetime(2026, 3, 1),
            weather_summary="sunny",
            markets_summary="BTC $67,000",
            meditation_text="Test.",
            poem=poem,
        )
        assert "real French poem excerpt" in prompt
        assert "Victor Hugo" in prompt
        assert "Demain, des l'aube" in prompt
        assert poem["excerpt"] in prompt


# -- Main generation function -------------------------------------------------

class TestGenerateViaClaudeCode:
    """Tests for the claude-code backend (subprocess calling ``claude -p``)."""

    def _mock_proc(self, result_dict, returncode=0, stderr=""):
        """Create a mock CompletedProcess with a CLI JSON envelope."""
        envelope = {"result": json.dumps(result_dict), "is_error": False}
        return MagicMock(
            returncode=returncode,
            stdout=json.dumps(envelope),
            stderr=stderr,
        )

    def test_successful_generation(self):
        proc = self._mock_proc(MOCK_API_RESPONSE)
        with patch("morning_report.french_gen.subprocess.run", return_value=proc):
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                date=datetime(2026, 3, 1),
            )

        assert result["meditation_fr"] == MOCK_API_RESPONSE["meditation_fr"]
        assert "_error" not in result
        assert result["_backend"] == "claude-code"
        assert result["_model"] == "opus"

    def test_missing_keys_get_fallback(self):
        partial = {"meditation_fr": "Texte traduit."}
        proc = self._mock_proc(partial)
        with patch("morning_report.french_gen.subprocess.run", return_value=proc):
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
            )

        assert result["meditation_fr"] == "Texte traduit."
        for key in ("history", "vocabulary", "expression", "grammar", "exercise"):
            assert result[key] == _FALLBACK_MSG

    def test_claude_not_installed(self):
        with patch(
            "morning_report.french_gen.subprocess.run",
            side_effect=FileNotFoundError("claude"),
        ), patch("morning_report.french_gen.time.sleep"):
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
            )

        assert "_error" in result
        assert "not found" in result["_error"]
        for key in _EXPECTED_KEYS:
            assert result[key] == _FALLBACK_MSG

    def test_timeout(self):
        with patch(
            "morning_report.french_gen.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=300),
        ), patch("morning_report.french_gen.time.sleep"):
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
            )

        assert "_error" in result
        for key in _EXPECTED_KEYS:
            assert result[key] == _FALLBACK_MSG

    def test_nonzero_exit(self):
        proc = MagicMock(returncode=1, stdout="", stderr="Something went wrong")
        with patch("morning_report.french_gen.subprocess.run", return_value=proc), \
             patch("morning_report.french_gen.time.sleep"):
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
            )

        assert "_error" in result

    def test_custom_model(self):
        proc = self._mock_proc(MOCK_API_RESPONSE)
        with patch("morning_report.french_gen.subprocess.run", return_value=proc) as mock_run:
            generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                model="sonnet",
            )

        args = mock_run.call_args[0][0]
        model_idx = args.index("--model")
        assert args[model_idx + 1] == "sonnet"

    def test_default_model_is_opus(self):
        proc = self._mock_proc(MOCK_API_RESPONSE)
        with patch("morning_report.french_gen.subprocess.run", return_value=proc) as mock_run:
            generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
            )

        args = mock_run.call_args[0][0]
        model_idx = args.index("--model")
        assert args[model_idx + 1] == "opus"

    def test_prompt_passed_via_stdin(self):
        """Verify user prompt is passed via stdin, not as a CLI argument."""
        proc = self._mock_proc(MOCK_API_RESPONSE)
        with patch("morning_report.french_gen.subprocess.run", return_value=proc) as mock_run:
            generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                date=datetime(2026, 3, 1),
            )

        call_kwargs = mock_run.call_args
        # Prompt should be in the 'input' kwarg, not in the command args
        assert call_kwargs.kwargs.get("input") is not None
        args = call_kwargs[0][0]
        # The command should be ["claude", "-p", "--system-prompt", ...] without
        # the user prompt embedded in it
        assert args[0] == "claude"
        assert args[1] == "-p"
        assert args[2] == "--system-prompt"  # no user prompt between -p and --system-prompt


class TestRetryLogic:
    """Tests for retry behaviour on failure."""

    def _mock_proc(self, result_dict):
        envelope = {"result": json.dumps(result_dict), "is_error": False}
        return MagicMock(
            returncode=0,
            stdout=json.dumps(envelope),
            stderr="",
        )

    def test_retry_succeeds_on_second_attempt(self):
        """First call times out, second succeeds."""
        proc = self._mock_proc(MOCK_API_RESPONSE)
        with patch(
            "morning_report.french_gen.subprocess.run",
            side_effect=[
                subprocess.TimeoutExpired(cmd="claude", timeout=300),
                proc,
            ],
        ), patch("morning_report.french_gen.time.sleep") as mock_sleep:
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                date=datetime(2026, 3, 1),
            )

        assert result["meditation_fr"] == MOCK_API_RESPONSE["meditation_fr"]
        assert "_error" not in result
        mock_sleep.assert_called_once_with(30)

    def test_retry_succeeds_on_third_attempt(self):
        """Two failures then success."""
        proc = self._mock_proc(MOCK_API_RESPONSE)
        with patch(
            "morning_report.french_gen.subprocess.run",
            side_effect=[
                subprocess.TimeoutExpired(cmd="claude", timeout=300),
                subprocess.TimeoutExpired(cmd="claude", timeout=300),
                proc,
            ],
        ), patch("morning_report.french_gen.time.sleep") as mock_sleep:
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                date=datetime(2026, 3, 1),
            )

        assert result["meditation_fr"] == MOCK_API_RESPONSE["meditation_fr"]
        assert "_error" not in result
        assert mock_sleep.call_count == 2

    def test_all_retries_exhausted(self):
        """Every attempt fails — error result returned."""
        with patch(
            "morning_report.french_gen.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=300),
        ), patch("morning_report.french_gen.time.sleep") as mock_sleep:
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                date=datetime(2026, 3, 1),
            )

        assert "_error" in result
        for key in _EXPECTED_KEYS:
            assert result[key] == _FALLBACK_MSG
        # One sleep between each pair of attempts, so one fewer than the attempts.
        assert mock_sleep.call_count == _MAX_RETRIES - 1

    def test_no_retry_on_success(self):
        """Successful first attempt — no retries."""
        proc = self._mock_proc(MOCK_API_RESPONSE)
        with patch(
            "morning_report.french_gen.subprocess.run",
            return_value=proc,
        ), patch("morning_report.french_gen.time.sleep") as mock_sleep:
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                date=datetime(2026, 3, 1),
            )

        assert "_error" not in result
        mock_sleep.assert_not_called()

    def test_nonzero_exit_triggers_retry(self):
        """Non-zero exit code also triggers retry."""
        bad_proc = MagicMock(returncode=1, stdout="", stderr="error")
        good_proc = self._mock_proc(MOCK_API_RESPONSE)
        with patch(
            "morning_report.french_gen.subprocess.run",
            side_effect=[bad_proc, good_proc],
        ), patch("morning_report.french_gen.time.sleep"):
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                date=datetime(2026, 3, 1),
            )

        assert result["meditation_fr"] == MOCK_API_RESPONSE["meditation_fr"]
        assert "_error" not in result


class TestPoemStamping:
    """Tests that a curated poem is stamped onto the result dict."""

    SAMPLE_POEM = {
        "title": "Demain, des l'aube",
        "author": "Victor Hugo",
        "source": "Les Contemplations (1856)",
        "excerpt": "Demain, des l'aube, a l'heure ou blanchit la campagne,",
        "themes": ["nature"],
    }

    def _mock_proc(self, result_dict):
        envelope = {"result": json.dumps(result_dict), "is_error": False}
        return MagicMock(
            returncode=0,
            stdout=json.dumps(envelope),
            stderr="",
        )

    def test_poem_stamped_on_result(self):
        proc = self._mock_proc(MOCK_API_RESPONSE)
        with patch("morning_report.french_gen.subprocess.run", return_value=proc):
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                date=datetime(2026, 3, 1),
                poem=self.SAMPLE_POEM,
            )

        assert result["poem"]["text"] == self.SAMPLE_POEM["excerpt"]
        assert result["poem"]["author"] == self.SAMPLE_POEM["author"]
        assert result["poem"]["title"] == self.SAMPLE_POEM["title"]
        assert result["poem"]["source"] == self.SAMPLE_POEM["source"]

    def test_no_poem_when_none_provided(self):
        proc = self._mock_proc(MOCK_API_RESPONSE)
        with patch("morning_report.french_gen.subprocess.run", return_value=proc):
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                date=datetime(2026, 3, 1),
                poem=None,
            )

        assert "poem" not in result


# -- Authentication handling ---------------------------------------------------

# The exact envelope `claude -p` writes to stdout when its OAuth session has
# expired: exit code 1, empty stderr, and the real reason buried in "result".
AUTH_FAILURE_STDOUT = json.dumps({
    "type": "result",
    "subtype": "success",
    "is_error": True,
    "api_error_status": None,
    "duration_ms": 18,
    "result": "Failed to authenticate: OAuth session expired and could not be refreshed",
})


class TestCliErrorMessage:
    """The reason for a failure has to survive into the log."""

    def test_extracts_result_field_from_error_envelope(self):
        proc = MagicMock(returncode=1, stdout=AUTH_FAILURE_STDOUT, stderr="")
        assert _cli_error_message(proc) == (
            "Failed to authenticate: OAuth session expired and could not be refreshed"
        )

    def test_appends_api_error_status_when_present(self):
        proc = MagicMock(
            returncode=1,
            stdout=json.dumps({"is_error": True, "result": "Unauthorized", "api_error_status": 401}),
            stderr="",
        )
        assert _cli_error_message(proc) == "Unauthorized (HTTP 401)"

    def test_falls_back_to_stderr_when_stdout_is_not_json(self):
        proc = MagicMock(returncode=1, stdout="not json at all", stderr="boom")
        assert _cli_error_message(proc) == "boom"

    def test_reports_absence_rather_than_an_empty_string(self):
        proc = MagicMock(returncode=1, stdout="", stderr="")
        assert _cli_error_message(proc) == "no error detail on stdout or stderr"


class TestIsAuthError:
    @pytest.mark.parametrize("message", [
        "Failed to authenticate: OAuth session expired and could not be refreshed",
        "Unauthorized (HTTP 401)",
        "Invalid API key · Please run /login",
    ])
    def test_recognises_auth_failures(self, message):
        assert _is_auth_error(message) is True

    @pytest.mark.parametrize("message", [
        "claude CLI timed out after 180s",
        "Connection reset by peer",
        "no error detail on stdout or stderr",
    ])
    def test_leaves_other_failures_retryable(self, message):
        assert _is_auth_error(message) is False


class TestAuthFailureStopsRetrying:
    def test_auth_failure_attempts_once(self):
        """Retrying an expired credential cannot help, so it must not burn the budget."""
        proc = MagicMock(returncode=1, stdout=AUTH_FAILURE_STDOUT, stderr="")
        with patch("morning_report.french_gen.subprocess.run", return_value=proc) as mock_run, \
             patch("morning_report.french_gen.time.sleep") as mock_sleep:
            result = generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                date=datetime(2026, 3, 1),
            )

        assert mock_run.call_count == 1
        mock_sleep.assert_not_called()
        assert "OAuth session expired" in result["_error"]
        assert "_fatal" not in result  # internal flag, not part of the report data
        for key in _EXPECTED_KEYS:
            assert result[key] == _FALLBACK_MSG

    def test_non_auth_failure_still_retries(self):
        proc = MagicMock(returncode=1, stdout="", stderr="transient network wobble")
        with patch("morning_report.french_gen.subprocess.run", return_value=proc) as mock_run, \
             patch("morning_report.french_gen.time.sleep"):
            generate_french_content(
                WEATHER_DATA, MARKETS_DATA, MEDITATION_DATA,
                date=datetime(2026, 3, 1),
            )

        assert mock_run.call_count == _MAX_RETRIES


class TestBuildCliEnv:
    def test_supplies_token_from_keychain(self):
        with patch.dict("os.environ", {}, clear=True), \
             patch("morning_report.french_gen.keychain.get_claude_token", return_value="tok-abc"):
            env = _build_cli_env()

        assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok-abc"

    def test_existing_env_token_wins_over_keychain(self):
        with patch.dict("os.environ", {"CLAUDE_CODE_OAUTH_TOKEN": "tok-env"}, clear=True), \
             patch("morning_report.french_gen.keychain.get_claude_token", return_value="tok-keychain"):
            env = _build_cli_env()

        assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "tok-env"

    def test_no_token_anywhere_leaves_var_unset(self):
        with patch.dict("os.environ", {}, clear=True), \
             patch("morning_report.french_gen.keychain.get_claude_token", return_value=None):
            env = _build_cli_env()

        assert "CLAUDE_CODE_OAUTH_TOKEN" not in env

    def test_strips_claudecode_and_api_key(self):
        with patch.dict(
            "os.environ",
            {"CLAUDECODE": "1", "ANTHROPIC_API_KEY": "sk-ant-x", "PATH": "/usr/bin"},
            clear=True,
        ), patch("morning_report.french_gen.keychain.get_claude_token", return_value=None):
            env = _build_cli_env()

        assert "CLAUDECODE" not in env
        assert "ANTHROPIC_API_KEY" not in env
        assert env["PATH"] == "/usr/bin"
