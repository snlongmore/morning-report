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

- [x] Markets gatherer (CoinGecko batched /simple/price + yfinance for stocks/indices)
- [x] GitHub gatherer (gh CLI: notifications, PRs needing review, assigned issues)
- [x] News gatherer (RSS via feedparser: Astronomy, AI/ML, Shipping, Crypto)
- [x] Weather gatherer (OpenWeatherMap current + 24h forecast, known coords for West Kirby)
- [x] CLI registration (all 8 gatherers)
- [x] Report template (full sections for markets, github, news, weather)
- [x] Config updated (corrected CoinGecko IDs, yfinance tickers, news feeds)
- [x] Tests (75 total: +39 for new gatherers)
- [x] Verification: full end-to-end run — all gatherers working live

### Sprint 3 Notes
- CoinGecko ID for Allora is `allora` (not `allora-network`)
- yfinance proxy for Vanguard FTSE Global All Cap: `VWRL.L` (Vanguard FTSE All-World ETF)
- Weather uses known coordinates for West Kirby to avoid geocoding API calls
- GitHub gatherer uses `gh` CLI with JSON output for notifications, PRs, issues
- News gatherer groups by category with configurable max per category
- Weather gracefully skips without API key; news raises if feedparser missing

## Sprint 4: Intelligence Layer + Skill

- [x] Claude Code skill (`/morning-report`) — installed to `~/.claude/skills/morning-report/skill.md`
- [x] MCP service discovery: Slack (Allora), Linear (Research + Quant teams), Jira (BolgiaTen: EOVT1, IF), Fireflies
- [x] Response drafting — built into skill Step 5 (drafts responses for high-priority items)
- [x] Meeting prep — built into skill Step 6 (cross-references calendar with Fireflies, Slack, Linear, Jira)
- [x] Priority ranking — built into skill Step 4 (cross-source urgency scoring: 5-point scale)
- [x] Config updated with MCP service identifiers (Slack user ID, Linear team IDs, Jira cloud ID)
- [x] Project CLAUDE.md updated with skill documentation
- [x] Settings updated with MCP tool permissions

### Sprint 4 Notes
- Skill orchestrates two execution modes: full (CLI + MCP) and quick (CLI only)
- Priority scoring: calendar urgency (+5), overdue tickets (+5), VIP messages (+4), blocking PRs (+4), high-priority tickets (+3)
- Slack queries: DMs (to:me), mentions (@user), with thread drill-down for important messages
- Linear: focuses on Research and Quant teams. Issues filtered by state (in-progress, unstarted)
- Jira: BolgiaTen cloud ID `deafb2cc-bf29-4c9c-a266-3f8f3ef826e0`. Projects: EOVT1 (EO-VTI), IF (Ideas Funnel)
- Fireflies: connected via snl@bolgiaten.com, no transcripts yet — gracefully skips
- All MCP sources are optional — skill degrades gracefully if any service is unavailable
- Skill does NOT send messages automatically — only drafts responses for user review
