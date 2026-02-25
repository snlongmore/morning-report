# Morning Report — Implementation Tracker

## Sprint 1: Foundation + Highest-Value Gatherers

- [x] Project scaffolding (pyproject.toml, directories, CLAUDE.md, .gitignore)
- [x] Config system (YAML loader with env var expansion)
- [x] Base gatherer interface (ABC)
- [x] Email gatherer (Apple Mail via AppleScript — unified inbox)
- [x] Calendar gatherer (macOS Calendar via Swift/EventKit — replaced AppleScript due to timeout)
- [x] Report generator (Jinja2 template with HH:MM time formatting)
- [x] CLI (Typer: gather, show, run commands)
- [ ] ADS token setup documentation
- [x] Verification: email (17 unread / 4 accounts) + calendar (20 events / 3 days) — live-tested

### Sprint 1 Notes
- AppleScript `inbox of account` fails for some account types → switched to application-level unified inbox
- Message body (`content of msg`) causes 60s+ timeouts → removed snippet extraction, subject+sender is sufficient
- AppleScript `Calendar.app` whose-clause times out on large calendars → replaced with Swift/EventKit (`helpers/calendar_events.swift`)
- EventKit returns ISO dates, making today/upcoming partitioning trivial

## Sprint 2: Research Tools
- [ ] ADS gatherer (metrics + delta tracking)
- [ ] arXiv gatherer (paper fetching + tier classification)
- [ ] arXiv Tier 1 (citation cross-referencing via ADS)
- [ ] arXiv Tier 2/3 (keyword matching, summaries)

## Sprint 3: Markets + External
- [ ] Markets gatherer (CoinGecko + yfinance)
- [ ] GitHub gatherer (notifications, PRs, issues)
- [ ] News gatherer (RSS)
- [ ] Weather gatherer (OpenWeatherMap)

## Sprint 4: Intelligence Layer + Skill
- [ ] Claude Code skill (`/morning-report`)
- [ ] Response drafting
- [ ] Meeting prep (Fireflies)
- [ ] Priority ranking (cross-source urgency)
