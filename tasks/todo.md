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

- [x] ADS gatherer (metrics + delta tracking) — gracefully skips without token
- [x] arXiv gatherer (paper fetching from 4 astro-ph categories)
- [x] arXiv Tier 1 (citation cross-referencing via ADS citations() operator) — needs ADS token
- [x] arXiv Tier 2/3 (keyword matching: CMZ, star formation, prebiotic, etc.)
- [x] arXiv PDF download (Tier 1 + Tier 2 papers)
- [x] Report template: structured arXiv briefing with tier sections
- [x] Verification: 41 new papers, 7 Tier 2, 1 Tier 3, 7 PDFs downloaded — live-tested

### Sprint 2 Notes
- ADS metrics endpoint requires bibcodes → 2-step: search for author bibcodes, then POST to /v1/metrics
- ADS delta tracking via `briefings/ads_history.json` — compares indicators + citations to previous day
- arXiv API supports native date filtering: `submittedDate:[YYYYMMDD TO YYYYMMDD]`
- Tier dict keys must be strings (not ints) to survive JSON round-tripping for Jinja2 templates
- arXiv papers are deduplicated by canonical ID (cross-listed papers appear in multiple categories)
- Tier 1 has inherent lag: new arXiv papers take days to appear in ADS → search ADS for last 7 days

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
