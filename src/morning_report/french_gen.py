"""French content generation via Claude Code CLI.

Makes a single LLM call to generate all French learning content for the
daily report: meditation translation, poem, historical note, vocabulary,
expression, grammar point, and exercise.

Uses ``claude -p`` (non-interactive print mode), covered by a Claude Code
subscription with no extra API charges.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from datetime import datetime
from typing import Any

from morning_report import keychain

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "opus"  # model alias for claude -p
# A successful generation takes around 40s, so 180s is generous. The bound that
# actually matters is that the whole retry budget, _MAX_RETRIES * (_CLI_TIMEOUT
# + _RETRY_DELAY), has to fit inside the 1200s pipeline watchdog in
# scripts/run-morning-report.sh. At 5 * (180 + 30) = 1050s it does. It did not
# with the previous 10 * (300 + 30) = 3300s, so a bad morning was killed
# mid-retry by the watchdog instead of finishing and writing a report.
_CLI_TIMEOUT = 180       # seconds for subprocess
_MAX_RETRIES = 5         # retry attempts on failure
_RETRY_DELAY = 30        # seconds between retries

_FALLBACK_MSG = "Section indisponible — erreur lors de la generation."

# Keys expected in the API response JSON
_EXPECTED_KEYS = (
    "meditation_fr",
    "history",
    "vocabulary",
    "expression",
    "grammar",
    "exercise",
)


def _build_system_prompt(level: str) -> str:
    """Build the system prompt for the French content generator."""
    return (
        f"You are a French language teacher preparing a daily learning document "
        f"for a student at CEFR level {level}. All generated French text must be "
        f"appropriate for that level. Respond ONLY with a JSON object — no markdown "
        f"fences, no commentary."
    )


def _build_user_prompt(
    date: datetime,
    weather_summary: str,
    markets_summary: str,
    meditation_text: str,
    poem: dict | None = None,
) -> str:
    """Build the user prompt with the day's data."""
    date_str = date.strftime("%A, %d %B %Y")

    if poem:
        poem_block = (
            f'\nThe following real French poem excerpt will appear in today\'s document. '
            f'Reference vocabulary and constructions from this poem in the vocabulary, '
            f'grammar, and exercise sections where natural:\n\n'
            f'"{poem["excerpt"]}" — {poem["author"]}, {poem["title"]}\n'
        )
    else:
        poem_block = ""

    return f"""Date: {date_str}

Weather: {weather_summary}

Markets: {markets_summary}

Meditation (English, full text):
{meditation_text}
{poem_block}
Generate a JSON object with these keys:

1. "meditation_fr": Full French translation of the meditation text above. Translate the ENTIRE text — no truncation, no summary.

2. "history": A notable event that happened on this date in history, written in French (2–3 sentences). Format: {{"year": NNNN, "text": "..."}}

3. "vocabulary": A list of 5–8 French vocabulary words drawn from TODAY'S weather, markets, meditation, or poem content. Each entry: {{"fr": "...", "en": "...", "example": "..."}} where example is a French sentence using the word.

4. "expression": A French idiomatic expression related to today's content. Format: {{"fr": "...", "en": "...", "example": "..."}}

5. "grammar": A grammar point illustrated by a construction that appears in the meditation translation or poem. Format: {{"rule": "...", "explanation": "...", "examples": ["...", "..."]}}

6. "exercise": A mini-exercise (fill-in-the-blank or translation) using today's vocabulary. Format: {{"instruction": "...", "questions": ["...", "..."], "answers": ["...", "..."]}}"""


def _extract_json(text: str) -> dict[str, Any]:
    """Parse JSON from the API response, handling code-block wrapping."""
    text = text.strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    if "```" in text:
        lines = text.split("\n")
        in_block = False
        block_lines: list[str] = []
        for line in lines:
            if line.strip().startswith("```") and not in_block:
                in_block = True
                continue
            elif line.strip().startswith("```") and in_block:
                break
            elif in_block:
                block_lines.append(line)
        if block_lines:
            try:
                return json.loads("\n".join(block_lines))
            except json.JSONDecodeError:
                pass

    # Fallback: return raw text as meditation_fr
    logger.warning("Could not parse JSON from response, using raw text as meditation_fr")
    return {"meditation_fr": text, "_parse_error": True}


def _weather_summary(weather_data: dict) -> str:
    """Build a one-line weather summary from gathered data."""
    if weather_data.get("status") != "ok":
        return "Weather data unavailable."

    for loc_name, loc_data in weather_data.get("locations", {}).items():
        current = loc_data.get("current", {})
        if current:
            desc = current.get("description", "")
            temp = current.get("temp", "")
            return f"{loc_name}: {desc}, {temp}°C"

    return "Weather data unavailable."


def _markets_summary(markets_data: dict) -> str:
    """Build a one-line markets summary from gathered data."""
    if markets_data.get("status") != "ok":
        return "Markets data unavailable."

    parts: list[str] = []
    for coin_id, coin_data in markets_data.get("crypto", {}).items():
        price = coin_data.get("price_usd")
        symbol = coin_data.get("symbol", coin_id).upper()
        if price is not None:
            if price >= 100:
                parts.append(f"{symbol} ${price:,.0f}")
            else:
                parts.append(f"{symbol} ${price:.4f}")

    return ", ".join(parts) if parts else "Markets data unavailable."


def _meditation_text(meditation_data: dict) -> str:
    """Extract the meditation text from gathered data."""
    if meditation_data.get("status") != "ok":
        return "Meditation text unavailable."

    items = meditation_data.get("items", [])
    if not items:
        return "No meditation entry found today."

    med = items[0]
    return med.get("content") or med.get("summary") or "Meditation text empty."


def _build_cli_env() -> dict[str, str]:
    """Build the environment for the ``claude -p`` subprocess.

    Strips ``CLAUDECODE`` so ``claude -p`` does not refuse to run when invoked
    from inside an interactive Claude Code session. The ``-p`` flag is
    non-interactive print mode with ``--no-session-persistence``, so there is no
    resource conflict with the parent session. Strips ``ANTHROPIC_API_KEY`` so
    the run bills against the Claude subscription rather than an API key.

    Supplies ``CLAUDE_CODE_OAUTH_TOKEN`` from the Keychain when it is not
    already in the environment. Without it, an unattended run depends on the
    short-lived OAuth access token that ``claude`` maintains for interactive
    use, and that token cannot be refreshed from a launchd job.
    """
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "ANTHROPIC_API_KEY")}

    if not env.get("CLAUDE_CODE_OAUTH_TOKEN"):
        token = keychain.get_claude_token()
        if token:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = token
        else:
            logger.warning(
                "No long-lived Claude token in the Keychain (service: %s). Falling back "
                "to the interactive OAuth session, which cannot be refreshed from an "
                "unattended run. Store one with: morning-report set-claude-token",
                keychain.CLAUDE_TOKEN_SERVICE,
            )

    return env


def _cli_error_message(proc: subprocess.CompletedProcess) -> str:
    """Pull the human-readable reason out of a failed ``claude -p`` run.

    On failure the CLI still writes its JSON envelope to stdout and leaves
    stderr empty, so the useful text ("Failed to authenticate: OAuth session
    expired...") sits in the envelope's ``result`` field. Reporting stderr
    alone produced log lines that said only "(no stderr)".
    """
    stdout = (proc.stdout or "").strip()
    if stdout:
        try:
            envelope = json.loads(stdout)
        except (json.JSONDecodeError, TypeError):
            pass
        else:
            if isinstance(envelope, dict) and envelope.get("is_error"):
                message = envelope.get("result")
                if isinstance(message, str) and message.strip():
                    status = envelope.get("api_error_status")
                    if status:
                        return f"{message.strip()} (HTTP {status})"
                    return message.strip()

    stderr = (proc.stderr or "").strip()
    return stderr or "no error detail on stdout or stderr"


def _is_auth_error(message: str) -> bool:
    """Whether a CLI error is an authentication failure.

    Retrying these is pointless: the credential will not repair itself between
    attempts, and burning the whole retry budget on it only delays the report.
    """
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in ("authenticate", "oauth", "unauthorized", "http 401", "please run /login")
    )


def _generate_via_claude_code(
    system_prompt: str,
    user_prompt: str,
    model: str,
) -> dict[str, Any]:
    """Generate French content using the Claude Code CLI (``claude -p``).

    Returns:
        Parsed content dict on success, or fallback dict with ``_error`` key.
    """
    env = _build_cli_env()

    try:
        proc = subprocess.run(
            [
                "claude", "-p",
                "--system-prompt", system_prompt,
                "--model", model,
                "--output-format", "json",
                "--tools", "",
                "--no-session-persistence",
            ],
            input=user_prompt,
            capture_output=True,
            text=True,
            timeout=_CLI_TIMEOUT,
            env=env,
        )
    except FileNotFoundError:
        logger.error("claude CLI not found on PATH — is Claude Code installed?")
        return {key: _FALLBACK_MSG for key in _EXPECTED_KEYS} | {
            "_error": "claude CLI not found on PATH"
        }
    except subprocess.TimeoutExpired:
        logger.error("claude CLI timed out after %ds", _CLI_TIMEOUT)
        return {key: _FALLBACK_MSG for key in _EXPECTED_KEYS} | {
            "_error": f"claude CLI timed out after {_CLI_TIMEOUT}s"
        }

    if proc.returncode != 0:
        message = _cli_error_message(proc)
        logger.error("claude CLI exited with code %d: %s", proc.returncode, message)
        result = {key: _FALLBACK_MSG for key in _EXPECTED_KEYS} | {
            "_error": f"claude CLI exited with code {proc.returncode}: {message}"
        }
        if _is_auth_error(message):
            result["_fatal"] = True
        return result

    # Parse the CLI JSON envelope → extract the "result" field
    try:
        envelope = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("Failed to parse claude CLI JSON output: %s", e)
        return {key: _FALLBACK_MSG for key in _EXPECTED_KEYS} | {
            "_error": f"Failed to parse CLI JSON output: {e}"
        }

    raw_text = envelope.get("result", "")
    return _extract_json(raw_text)


def generate_french_content(
    weather_data: dict,
    markets_data: dict,
    meditation_data: dict,
    level: str = "B1",
    model: str | None = None,
    date: datetime | None = None,
    poem: dict | None = None,
) -> dict[str, Any]:
    """Generate all French learning content via a single LLM call.

    Uses ``claude -p`` with retry logic: on failure (timeout, non-zero exit,
    or other error), waits and retries up to ``_MAX_RETRIES`` times.

    Args:
        weather_data: Gathered weather data dict.
        markets_data: Gathered markets data dict.
        meditation_data: Gathered meditation data dict.
        level: CEFR level (A1-C2).
        model: Model alias for claude -p (e.g. ``"opus"``, ``"sonnet"``).
            Defaults to ``"opus"``.
        date: Date for the report. Defaults to today.
        poem: Curated poem dict (from :func:`poems.select_poem`). If provided,
            the poem is passed to the LLM as context and stamped onto the result.

    Returns:
        Dict with keys: meditation_fr, poem, history, vocabulary, expression,
        grammar, exercise. Each value is a string or structured dict. On error,
        values contain fallback messages and an _error key is set.
    """
    date = date or datetime.now()
    model = model or _DEFAULT_MODEL

    # Build summaries from gathered data
    w_summary = _weather_summary(weather_data)
    m_summary = _markets_summary(markets_data)
    med_text = _meditation_text(meditation_data)

    system_prompt = _build_system_prompt(level)
    user_prompt = _build_user_prompt(date, w_summary, m_summary, med_text, poem=poem)

    # Try with retries
    result = None
    for attempt in range(1, _MAX_RETRIES + 1):
        result = _generate_via_claude_code(system_prompt, user_prompt, model)

        if not result.get("_error"):
            break  # Success

        if result.pop("_fatal", False):
            logger.error(
                "Authentication failed, so retrying will not help: %s. Store a "
                "long-lived token with: morning-report set-claude-token",
                result["_error"],
            )
            break

        if attempt < _MAX_RETRIES:
            logger.warning(
                "Attempt %d/%d failed (%s), retrying in %ds...",
                attempt, _MAX_RETRIES, result["_error"], _RETRY_DELAY,
            )
            time.sleep(_RETRY_DELAY)
        else:
            logger.error(
                "All %d attempts failed. Last error: %s",
                _MAX_RETRIES, result["_error"],
            )

    # Fill in any missing keys with fallback
    for key in _EXPECTED_KEYS:
        if key not in result:
            result[key] = _FALLBACK_MSG

    # Stamp the curated poem onto the result (not LLM-generated)
    if poem:
        result["poem"] = {
            "text": poem["excerpt"],
            "author": poem["author"],
            "title": poem["title"],
            "source": poem["source"],
        }

    result["_backend"] = "claude-code"
    result["_model"] = model
    return result
