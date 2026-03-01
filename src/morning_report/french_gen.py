"""French content generation via Claude Code CLI or Anthropic API.

Makes a single LLM call to generate all French learning content for the
daily report: meditation translation, poem, historical note, vocabulary,
expression, grammar point, and exercise.

Two backends are supported:
- ``claude-code`` (default): uses ``claude -p`` (non-interactive print mode),
  covered by a Claude Code subscription with no extra API charges.
- ``api``: uses the ``anthropic`` SDK directly, requires a separate API key
  and per-token billing.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_CLI = "sonnet"           # model alias for claude -p
_DEFAULT_MODEL_API = "claude-haiku-4-5" # full model ID for anthropic SDK
_MAX_TOKENS = 4096
_TIMEOUT = 120.0
_CLI_TIMEOUT = 180  # seconds for subprocess
_TEMPERATURE = 0.7

_FALLBACK_MSG = "Section indisponible — erreur lors de la generation."

# Keys expected in the API response JSON
_EXPECTED_KEYS = (
    "meditation_fr",
    "poem",
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
) -> str:
    """Build the user prompt with the day's data."""
    date_str = date.strftime("%A, %d %B %Y")
    return f"""Date: {date_str}

Weather: {weather_summary}

Markets: {markets_summary}

Meditation (English, full text):
{meditation_text}

Generate a JSON object with these keys:

1. "meditation_fr": Full French translation of the meditation text above. Translate the ENTIRE text — no truncation, no summary.

2. "poem": A short French poem (4–8 lines) related to today's themes (weather, season, or meditation topic). Include the poet's name (real or "Anonyme"). Format: {{"text": "...", "author": "..."}}

3. "history": A notable event that happened on this date in history, written in French (2–3 sentences). Format: {{"year": NNNN, "text": "..."}}

4. "vocabulary": A list of 5–8 French vocabulary words drawn from TODAY'S weather, markets, or meditation content. Each entry: {{"fr": "...", "en": "...", "example": "..."}} where example is a French sentence using the word.

5. "expression": A French idiomatic expression related to today's content. Format: {{"fr": "...", "en": "...", "example": "..."}}

6. "grammar": A grammar point illustrated by a construction that appears in the meditation translation or poem. Format: {{"rule": "...", "explanation": "...", "examples": ["...", "..."]}}

7. "exercise": A mini-exercise (fill-in-the-blank or translation) using today's vocabulary. Format: {{"instruction": "...", "questions": ["...", "..."], "answers": ["...", "..."]}}"""


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
    logger.warning("Could not parse JSON from API response, using raw text as meditation_fr")
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


def _generate_via_claude_code(
    system_prompt: str,
    user_prompt: str,
    model: str,
) -> dict[str, Any]:
    """Generate French content using the Claude Code CLI (``claude -p``).

    Returns:
        Parsed content dict on success, or fallback dict with ``_error`` key.
    """
    # Strip CLAUDECODE env var so `claude -p` doesn't refuse to run when
    # invoked from within an interactive Claude Code session.  The -p flag
    # is non-interactive print mode with --no-session-persistence, so there
    # is no resource conflict with the parent session.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    try:
        proc = subprocess.run(
            [
                "claude", "-p", user_prompt,
                "--system-prompt", system_prompt,
                "--model", model,
                "--output-format", "json",
                "--tools", "",
                "--no-session-persistence",
            ],
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
        stderr = proc.stderr.strip() if proc.stderr else "(no stderr)"
        stdout = proc.stdout.strip() if proc.stdout else "(no stdout)"
        logger.error(
            "claude CLI exited with code %d: stderr=%s stdout=%s",
            proc.returncode, stderr, stdout,
        )
        return {key: _FALLBACK_MSG for key in _EXPECTED_KEYS} | {
            "_error": f"claude CLI exited with code {proc.returncode}: {stderr}"
        }

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


def _generate_via_api(
    system_prompt: str,
    user_prompt: str,
    model: str,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Generate French content using the ``anthropic`` SDK directly.

    Returns:
        Parsed content dict on success, or fallback dict with ``_error`` key.
    """
    try:
        import anthropic
    except ImportError:
        logger.error("anthropic package not installed. Run: uv pip install 'morning-report[api]'")
        return {key: _FALLBACK_MSG for key in _EXPECTED_KEYS} | {
            "_error": "anthropic package not installed"
        }

    try:
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
    except anthropic.AuthenticationError:
        logger.error("Anthropic API key not found or invalid")
        return {key: _FALLBACK_MSG for key in _EXPECTED_KEYS} | {
            "_error": "Anthropic API key not found or invalid"
        }

    try:
        response = client.messages.create(
            model=model,
            max_tokens=_MAX_TOKENS,
            temperature=_TEMPERATURE,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            timeout=_TIMEOUT,
        )
    except Exception as e:
        logger.error("Anthropic API call failed: %s", e)
        return {key: _FALLBACK_MSG for key in _EXPECTED_KEYS} | {
            "_error": f"API call failed: {e}"
        }

    # Extract text from response
    raw_text = ""
    for block in response.content:
        if block.type == "text":
            raw_text += block.text

    return _extract_json(raw_text)


def generate_french_content(
    weather_data: dict,
    markets_data: dict,
    meditation_data: dict,
    level: str = "B1",
    model: str | None = None,
    api_key: str | None = None,
    backend: str = "claude-code",
    date: datetime | None = None,
) -> dict[str, Any]:
    """Generate all French learning content via a single LLM call.

    Args:
        weather_data: Gathered weather data dict.
        markets_data: Gathered markets data dict.
        meditation_data: Gathered meditation data dict.
        level: CEFR level (A1–C2).
        model: Model name/alias.  Defaults depend on backend:
            ``"haiku"`` for claude-code, ``"claude-haiku-4-5"`` for api.
        api_key: Anthropic API key (only used when ``backend="api"``).
        backend: ``"claude-code"`` (default) or ``"api"``.
        date: Date for the report. Defaults to today.

    Returns:
        Dict with keys: meditation_fr, poem, history, vocabulary, expression,
        grammar, exercise. Each value is a string or structured dict. On error,
        values contain fallback messages and an _error key is set.
    """
    date = date or datetime.now()

    if backend == "api":
        model = model or _DEFAULT_MODEL_API
    else:
        model = model or _DEFAULT_MODEL_CLI

    # Build summaries from gathered data
    w_summary = _weather_summary(weather_data)
    m_summary = _markets_summary(markets_data)
    med_text = _meditation_text(meditation_data)

    system_prompt = _build_system_prompt(level)
    user_prompt = _build_user_prompt(date, w_summary, m_summary, med_text)

    if backend == "api":
        result = _generate_via_api(system_prompt, user_prompt, model, api_key)
    else:
        result = _generate_via_claude_code(system_prompt, user_prompt, model)

    # Fill in any missing keys with fallback
    for key in _EXPECTED_KEYS:
        if key not in result:
            result[key] = _FALLBACK_MSG

    return result
