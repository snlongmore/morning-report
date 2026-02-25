# Morning Report — Project Instructions

## What This Is
An automated daily morning briefing system for Steve Longmore. Gathers data from email, calendar, ADS, arXiv, markets, GitHub, news, and weather; classifies, summarises, and produces a structured markdown report.

## Architecture
- **Python CLI** (`morning-report`) using Typer
- **Gatherers** (`src/morning_report/gatherers/`) — each implements `BaseGatherer` ABC
- **Report generator** (`src/morning_report/report/`) — Jinja2 template rendering
- **Config** (`config/config.yaml`) — YAML with env var expansion

## Key Conventions
- All gatherers return `dict` from `gather()` — JSON-serialisable
- AppleScript calls use `subprocess.run(["osascript", "-e", ...])` — never `os.system`
- Config secrets use `${ENV_VAR}` syntax, resolved at load time
- Reports written to `briefings/YYYY-MM-DD.md`
- Papers downloaded to `papers/YYYY-MM-DD/`
- Source code lives in `src/morning_report/` (src layout)

## Running
```bash
# Install in dev mode
uv pip install -e ".[dev]"

# Gather data and show report
morning-report gather
morning-report show

# Run specific gatherer
morning-report gather --only email
morning-report gather --only calendar
```

## Testing
```bash
pytest tests/
```
