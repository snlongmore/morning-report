# Morning Report — Sprint 2 Handoff

> **Written:** 2026-02-25 11:05 UTC | **Branch:** main | **Commits:** 2 (c8b61e0, 0dc9f8b)

## Current State

Sprints 1 and 2 are complete. The system gathers live data from Apple Mail (7 accounts), macOS Calendar (12 calendars), and arXiv (4 astro-ph categories), classifies papers into research-relevance tiers, downloads PDFs, and produces a structured markdown morning briefing. ADS metrics gathering is built but disabled pending API token setup. 36 tests passing.

**Working gatherers:** email, calendar, arxiv
**Built but needs token:** ads (gracefully skips)
**Not yet built:** markets, github, news, weather

## Decisions Made

### Sprint 1
- **AppleScript unified inbox** — per-account `inbox of acct` fails on Exchange/IMAP. Use application-level `inbox`, group by `account of mailbox of msg`.
- **No message body extraction** — `content of msg` causes 60s+ timeouts. Subject + sender sufficient for triage.
- **Swift/EventKit for calendar** — AppleScript `whose start date` times out on ~35 calendars. Swift helper at `helpers/calendar_events.swift` calls EventKit directly (instant).
- **src layout** — `src/morning_report/` with hatchling, editable install via `uv pip install -e ".[dev]"`.

### Sprint 2
- **ADS 2-step workflow** — search `/v1/search/query` for author bibcodes, then POST to `/v1/metrics` for aggregate indicators.
- **ADS delta tracking** — `briefings/ads_history.json` stores daily snapshots; deltas computed against most recent previous entry.
- **arXiv native date filtering** — `submittedDate:[YYYYMMDD TO YYYYMMDD]` avoids fetching entire history.
- **Tier dict string keys** — must use `"1"`, `"2"`, `"3"` (not ints) to survive JSON round-trip for Jinja2.
- **Tier 1 citation lag** — new arXiv papers take days to enter ADS. We query ADS for citations from last 7 days, not just today.
- **PDF downloads for Tier 1+2 only** — Tier 3 (COOL) gets listed but not downloaded by default.

## Files Modified

| File | Change |
|------|--------|
| `src/morning_report/gatherers/ads.py` | ADS metrics: bibcode search, /v1/metrics POST, delta tracking |
| `src/morning_report/gatherers/arxiv.py` | arXiv paper fetch, Atom XML parsing, tier integration, PDF download |
| `src/morning_report/arxiv/classifier.py` | Tier 1/2/3 classification: citations, keyword matching |
| `src/morning_report/arxiv/paper_handler.py` | PDF download to `papers/YYYY-MM-DD/` |
| `src/morning_report/cli.py` | Registered ads + arxiv gatherers, arxiv gets ads_config for Tier 1 |
| `src/morning_report/report/templates/morning_report.md.j2` | Structured arXiv + ADS sections in report |
| `tests/test_ads.py` | 6 tests: availability, metrics parsing, delta computation |
| `tests/test_arxiv.py` | 9 tests: classifier tiers, XML parsing, gatherer integration |
| `tasks/todo.md` | Sprint 2 items checked off |

## What's Been Tried

| Approach | Outcome |
|----------|---------|
| AppleScript `inbox of acct` per-account email | Failed — `-1728` on Exchange |
| AppleScript `content of msg` for snippets | Failed — 60s timeout |
| AppleScript Calendar `whose start date >= ...` | Failed — `-1712` timeout |
| Swift EventKit for calendar | Worked — instant, ISO dates |
| Application-level unified `inbox` for email | Worked — all 7 accounts |
| arXiv API date-range query | Worked — 41 papers fetched for one day |
| arXiv tier classification (keyword matching) | Worked — 7 Tier 2, 1 Tier 3 correctly classified |
| Integer keys in tier dict | Failed — Jinja2 template couldn't match after JSON round-trip |
| String keys `"1"/"2"/"3"` in tier dict | Worked — consistent across direct and JSON paths |

## Next Steps

1. **Sprint 3: Markets gatherer** — `gatherers/markets.py`
   - CoinGecko API (no auth): BTC, ETH, `allora-network`, `researchcoin` — verify ALLO/RSC IDs
   - yfinance: `^GSPC` (S&P 500), `^FTSE`, `^N225`, `0P0001IHIS.L` (VAFTGAG — verify ticker)
   - Add `yfinance` to `[project.optional-dependencies.markets]` (already in pyproject.toml)
2. **Sprint 3: GitHub gatherer** — `gatherers/github.py` via `gh` CLI or PyGithub
3. **Sprint 3: News gatherer** — `gatherers/news.py` via feedparser (RSS)
4. **Sprint 3: Weather gatherer** — `gatherers/weather.py` via OpenWeatherMap
5. **Sprint 4: Claude Code skill** — `/morning-report` wrapping CLI + MCP (Slack, Linear, Jira, Fireflies)
6. **ADS token** — user retrieves from https://ui.adsabs.harvard.edu/user/settings/token, sets `ADS_API_TOKEN`

## Blockers / Open Questions

- **ADS API token** — needed for ADS metrics + arXiv Tier 1 citation checking
- **VAFTGAG yfinance ticker** — verify exact identifier for Vanguard FTSE Global All Cap (`0P0001IHIS.L`?)
- **ALLO/RSC CoinGecko IDs** — verify `allora-network` and `researchcoin` exist on CoinGecko
- **Duplicate calendar events** — ARI Seminar appears in both "ARI colloquia" and "ARI Seminars"; consider dedup
- **GitHub repos list** — user needs to configure which repos to monitor
- **News RSS feeds** — need to curate feeds for shipping, AI/crypto, astronomy
- **OpenWeatherMap API key** — needed for weather gatherer

## Key File Locations

| What | Path |
|------|------|
| CLI entry point | `src/morning_report/cli.py` |
| Config loader | `src/morning_report/config.py` |
| Base gatherer ABC | `src/morning_report/gatherers/base.py` |
| Email gatherer | `src/morning_report/gatherers/email.py` |
| Calendar gatherer | `src/morning_report/gatherers/calendar.py` |
| Swift calendar helper | `src/morning_report/helpers/calendar_events.swift` |
| ADS gatherer | `src/morning_report/gatherers/ads.py` |
| arXiv gatherer | `src/morning_report/gatherers/arxiv.py` |
| Tier classifier | `src/morning_report/arxiv/classifier.py` |
| PDF handler | `src/morning_report/arxiv/paper_handler.py` |
| Report generator | `src/morning_report/report/generator.py` |
| Jinja2 template | `src/morning_report/report/templates/morning_report.md.j2` |
| Config template | `config/config.example.yaml` |
| Generated reports | `briefings/YYYY-MM-DD.md` |
| Downloaded papers | `papers/YYYY-MM-DD/` |
| ADS history | `briefings/ads_history.json` |
| Implementation tracker | `tasks/todo.md` |
