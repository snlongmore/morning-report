# Morning Report — Sprint 1 Handoff

> **Written:** 2026-02-25 10:40 UTC | **Branch:** main (no commits yet — initial commit pending)

## Current State

Sprint 1 is complete: project scaffolding, config system, email gatherer, calendar gatherer, report generator, CLI, and tests (21 passing). The system gathers live data from Apple Mail (17 unread across 4 accounts) and macOS Calendar (20 events over 3 days) and produces a structured markdown morning briefing. No commits have been made yet — all files are staged and ready for initial commit.

## Decisions Made

- **AppleScript unified inbox** — per-account `inbox of acct` fails on Exchange/IMAP accounts. Switched to application-level `inbox` which covers all 7 accounts.
- **No message body extraction** — fetching `content of msg` via AppleScript causes 60s+ timeouts. Subject + sender is sufficient for morning triage; the Claude skill layer (Sprint 4) will handle deeper analysis.
- **Swift/EventKit for calendar** — AppleScript Calendar `whose start date >= ...` times out on ~35 calendars. Replaced entirely with a Swift helper (`src/morning_report/helpers/calendar_events.swift`) that calls EventKit directly — returns results instantly.
- **src layout** — `src/morning_report/` with hatchling build backend, editable install via `uv pip install -e ".[dev]"`.

## Files Modified

| File | Change |
|------|--------|
| `pyproject.toml` | Project config: typer, pyyaml, jinja2, requests deps; hatchling build |
| `CLAUDE.md` | Project instructions for Claude Code sessions |
| `.gitignore` | Ignores briefings/, papers/, config.yaml, .venv, __pycache__ |
| `config/config.example.yaml` | Full config template with all 7 accounts, 12 calendars, arXiv categories |
| `config/config.yaml` | Live config (gitignored, copy of example) |
| `src/morning_report/__init__.py` | Package init, version 0.1.0 |
| `src/morning_report/config.py` | YAML loader with `${ENV_VAR}` expansion, project root helper |
| `src/morning_report/cli.py` | Typer CLI: `gather`, `show`, `run` commands with `--only` filter |
| `src/morning_report/gatherers/base.py` | BaseGatherer ABC: `gather()`, `safe_gather()`, `is_available()` |
| `src/morning_report/gatherers/email.py` | Apple Mail via AppleScript (unified inbox), VIP flagging, response heuristic |
| `src/morning_report/gatherers/calendar.py` | macOS Calendar via Swift/EventKit, today/upcoming partitioning |
| `src/morning_report/helpers/calendar_events.swift` | Swift EventKit helper — queries named calendars, returns JSON |
| `src/morning_report/report/generator.py` | Jinja2 report assembly, JSON data caching |
| `src/morning_report/report/templates/morning_report.md.j2` | Markdown template with HH:MM times, all-day handling |
| `tests/test_config.py` | 5 tests: env var expansion, config loading, fallback |
| `tests/test_email.py` | 9 tests: response heuristic, parsing, VIP flagging, empty inbox |
| `tests/test_calendar.py` | 7 tests: parsing, all-day events, error handling, access denied |

## What's Been Tried

| Approach | Outcome |
|----------|---------|
| AppleScript `inbox of acct` per-account email | Failed — `-1728` error on Exchange accounts |
| AppleScript `content of msg` for snippets | Failed — 60s timeout on unified inbox |
| AppleScript Calendar `whose start date >= ...` | Failed — AppleEvent timeout (`-1712`) on large calendars |
| Swift EventKit for calendar | Worked perfectly — instant results, ISO date format |
| Application-level unified `inbox` for email | Worked — finds all accounts, ~45s with no body extraction |

## Next Steps

1. **Get ADS API token** — User retrieves from https://ui.adsabs.harvard.edu/user/settings/token, sets as `ADS_API_TOKEN` env var
2. **Sprint 2: ADS gatherer** — `gatherers/ads.py`: query `api.adsabs.harvard.edu/v1/metrics` for "longmore, s.n.", track deltas in `briefings/ads_history.json`
3. **Sprint 2: arXiv gatherer** — `gatherers/arxiv.py` + `arxiv/classifier.py`: fetch new papers from astro-ph.{GA,SR,EP,IM}, tier classification (Tier 1: cites my work via ADS, Tier 2: CMZ/star formation keywords, Tier 3: COOL topics)
4. **Sprint 3: Markets** — CoinGecko (BTC, ETH, ALLO, RSC) + yfinance (S&P, FTSE, Nikkei, VAFTGAG)
5. **Sprint 4: Claude Code skill** — `/morning-report` wrapping CLI + MCP (Slack, Linear, Jira, Fireflies)

## Blockers / Open Questions

- **ADS API token** — needed before Sprint 2 ADS gatherer can be tested
- **VAFTGAG yfinance ticker** — need to verify exact identifier for Vanguard FTSE Global All Cap
- **ALLO/RSC CoinGecko IDs** — need to verify `allora-network` and `researchcoin` IDs
- **Duplicate calendar events** — some events appear in multiple calendars (e.g. ARI Seminar in both "ARI colloquia" and "ARI Seminars"). Consider deduplication by title+time.

## Key File Locations

| What | Path |
|------|------|
| CLI entry point | `src/morning_report/cli.py` |
| Config loader | `src/morning_report/config.py` |
| Base gatherer ABC | `src/morning_report/gatherers/base.py` |
| Email gatherer | `src/morning_report/gatherers/email.py` |
| Calendar gatherer | `src/morning_report/gatherers/calendar.py` |
| Swift calendar helper | `src/morning_report/helpers/calendar_events.swift` |
| Report generator | `src/morning_report/report/generator.py` |
| Jinja2 template | `src/morning_report/report/templates/morning_report.md.j2` |
| Config template | `config/config.example.yaml` |
| Live config (gitignored) | `config/config.yaml` |
| Generated reports | `briefings/YYYY-MM-DD.md` |
| Implementation tracker | `tasks/todo.md` |
