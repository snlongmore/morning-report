# Morning Report — Project Instructions

## What This Is
An automated daily French learning document generator. Gathers weather, markets, and a daily meditation; uses the Anthropic API to generate French translations, vocabulary, grammar, poetry, and exercises; produces a structured markdown document.

## Architecture
- **Python CLI** (`morning-report`) using Typer
- **Gatherers** (`src/morning_report/gatherers/`) — weather, markets, meditation (each implements `BaseGatherer` ABC)
- **French generator** (`src/morning_report/french_gen.py`) — single Anthropic API call for all French content
- **Report generator** (`src/morning_report/report/`) — Jinja2 template rendering
- **Config** (`config/config.yaml`) — YAML with env var expansion

## Key Conventions
- All gatherers return `dict` from `gather()` — JSON-serialisable
- Config secrets use `${ENV_VAR}` syntax, resolved at load time
- Reports written to `briefings/YYYY-MM-DD.md`
- Source code lives in `src/morning_report/` (src layout)
- French content generated via `claude-haiku-4-5` (configurable in `french.model`)

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
