# Morning Report — Project Instructions

## What This Is
An automated daily French learning document generator. Gathers weather, markets, and a daily meditation; uses Claude Code CLI (`claude -p`) to generate French translations, vocabulary, grammar, poetry, and exercises; produces a structured markdown document.

## Architecture
- **Python CLI** (`morning-report`) using Typer
- **Gatherers** (`src/morning_report/gatherers/`) — weather, markets, meditation (each implements `BaseGatherer` ABC)
- **French generator** (`src/morning_report/french_gen.py`) — single LLM call via `claude -p` for all French content, with retry logic
- **Report generator** (`src/morning_report/report/`) — Jinja2 template rendering
- **Config** (`config/config.yaml`) — YAML with env var expansion

## Key Conventions
- All gatherers return `dict` from `gather()` — JSON-serialisable
- Config secrets use `${ENV_VAR}` syntax, resolved at load time
- Reports written to `briefings/YYYY-MM-DD.md`
- Source code lives in `src/morning_report/` (src layout)
- French content generation uses `claude -p` CLI (covered by Claude Code subscription, no API key needed)
- Default model: `opus` (configurable via `french.model` in config)
- Retry logic: up to 5 attempts with 30s delay on failure (handles network issues after wake-from-sleep). Authentication failures are not retried, because the credential will not repair itself between attempts. The retry budget is sized to fit inside the 1200s pipeline watchdog in `scripts/run-morning-report.sh`, so if you raise either constant, check that `_MAX_RETRIES * (_CLI_TIMEOUT + _RETRY_DELAY)` still fits.

## Secrets

Both live in the login Keychain, because launchd can read it without a prompt and nothing here should depend on a shell rc file. Neither survives a machine rebuild, so both have to be set up again by hand on a new laptop.

| Secret | Keychain service | How to set it |
|--------|------------------|---------------|
| Gmail app password | `morning-report-gmail` | `morning-report set-password` (generate at https://myaccount.google.com/apppasswords) |
| Long-lived Claude token | `morning-report-claude-token` | `claude setup-token`, then `morning-report set-claude-token` |

The Claude token matters for the unattended run specifically. The OAuth access token that interactive Claude Code maintains lasts about 7.5 hours, and refreshing it does not work from a launchd job, so a scheduled run fails with `Failed to authenticate: OAuth session expired and could not be refreshed` whenever the token happened to expire overnight. A long-lived token from `claude setup-token` has no refresh step. The wrapper script exports it as `CLAUDE_CODE_OAUTH_TOKEN`, and `french_gen._build_cli_env()` also reads it from the Keychain directly so manual runs behave the same way.

## Running
```bash
# Install in dev mode
uv pip install -e ".[dev,markets]"

# Full pipeline: gather → generate → export → email
morning-report auto

# Step by step
morning-report gather                    # Fetch weather, markets, meditation
morning-report show                      # Generate + display French document
morning-report export                    # Convert to .docx via pandoc
morning-report email                     # Email the .docx

# Run specific gatherer
morning-report gather --only weather
morning-report gather --only meditation
```

## Testing
```bash
pytest tests/
```
