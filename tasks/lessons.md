# Lessons — Morning Report (Project-Specific)

## 2026-02-25: AppleScript `inbox of account` is unreliable — use unified inbox
Apple Mail's AppleScript `inbox of acct` property fails with `-1728` on some account types (Exchange, certain IMAP). The application-level `inbox` (unified inbox) works for all accounts. Per-account grouping can still be achieved by reading `name of account of mailbox of msg` on each message.

## 2026-02-25: AppleScript message body extraction causes timeouts — skip it
Fetching `content of msg` in AppleScript for even a small number of unread messages causes 60s+ timeouts on the unified inbox. Subject + sender is sufficient for morning triage; detailed content analysis belongs in the Claude skill layer, not the raw gatherer.

## 2026-02-25: AppleScript Calendar is unusably slow — use Swift/EventKit
AppleScript's `every event of cal whose start date >= today` iterates ALL events (including historical recurring events), causing AppleEvent timeouts (`-1712`) on calendars with any significant history. Swift/EventKit queries the CalendarKit database directly with proper date-range predicates and returns results instantly. Always prefer EventKit for macOS calendar access.

## 2026-02-25: EventKit requires explicit permission grant on first run
The Swift calendar helper prompts for calendar access permission on first run. This is a one-time macOS permission grant. If it fails silently, check System Settings > Privacy & Security > Calendars.

## 2026-02-25: Use string keys for tier dicts that pass through JSON
When a Python dict with integer keys (e.g. `{1: [...], 2: [...]}`) is serialised to JSON and loaded back, keys become strings (`{"1": [...], "2": [...]}`). Jinja2 templates that check `data.tiers['1']` will fail if the dict has integer keys. Always use string keys in dicts that may be JSON round-tripped — especially anything going into the report template.

## 2026-02-27: CLI commands use flags not positional args — check `--help` before guessing
`morning-report export briefings/2026-02-27.md` failed with "Got unexpected extra argument". The correct syntax is `morning-report export --date 2026-02-27 --french`. Always run `command --help` before guessing positional arguments, especially for Typer CLIs which default to option-style flags.

## 2026-02-27: RSS feeds may return stale content if fetched too early in the day
The Richard Rohr meditation RSS feed (CAC) sometimes returns yesterday's article if fetched before ~09:00 UTC. The CLI gather caches whatever it gets. If the skill notices stale content, re-run `morning-report gather` to refresh. Consider adding a freshness check (compare published date to today) in the meditation gatherer.

## 2026-02-27: Strip HTML from RSS content before storing in JSON
RSS `summary` and `content` fields often contain raw HTML (`<p>`, `<b>`, `<div>` tags). If stored as-is, the HTML renders badly in markdown reports and confuses LLM translation. Always strip HTML tags at the gatherer level with a simple regex (`re.sub(r"<[^>]+>", "", text)`) before writing to the JSON data file.

## 2026-02-27: Jinja2 custom filters are the right pattern for French translations
Rather than duplicating translation logic in the template or doing string replacement in Python, register custom Jinja2 filters (`env.filters["weather_fr"] = _weather_fr`) and call them in the template (`{{ description | weather_fr }}`). This keeps the template readable, the translation logic testable, and the fallback behaviour clean (return original string if no translation found).

## 2026-02-27: Remove placeholder sections from templates — use skill-only content instead
Empty "Section completee par le skill" placeholders in the Jinja2 template confused CLI-only users and looked broken. Skill-generated content (poem, history, vocabulary lesson) should only appear in the skill-written report, not as empty stubs in the template. The template should render a complete, clean report with whatever data is available.

## 2026-03-02: Stamp metadata on every return path when a function has early returns
When adding metadata (like `_backend`, `_model`) to a function's return value, audit every `return` statement — including early returns from fallback branches. The fallback path in `generate_french_content()` had an early `return fallback` that would have missed the metadata stamp without explicit handling. Rule: if a function has N return paths, metadata must be stamped on all N.

## 2026-03-02: Use `getattr` chains for SDK response objects — don't assume attribute presence
Anthropic SDK response objects have `response.usage.input_tokens`, but defensive `getattr(response, "usage", None)` is safer than direct access. SDK versions change, and error responses may omit usage entirely. Same principle applies to any third-party SDK object.

## 2026-03-02: Jinja2 default undefined silently returns falsy for missing dict keys
With Jinja2's default `Undefined` (not `StrictUndefined`), `dict._missing_key == "some_value"` evaluates to `False` without raising. This means you can write `{% if french_content._backend == "api" %}` without needing an explicit `is defined` guard, as long as the fallthrough behaviour is correct. But use `|default(0)` for numeric formatting to avoid `"%.4f"|format(Undefined)` errors.

## 2026-03-02: The project venv is at `.venv/` — use `.venv/bin/morning-report` not bare `morning-report`
The `morning-report` CLI is installed in the project's `.venv/`, not in the system Python. The system `python` (miniforge) doesn't have the package. Always use `.venv/bin/morning-report` or activate the venv first.

## 2026-03-26: feedparser.parse(url) has NO timeout — always fetch via requests first
`feedparser.parse(url)` does its own HTTP fetch with no timeout parameter and no way to set one. When the server is slow, returns a Cloudflare challenge, or drops the connection, it blocks indefinitely. The fix: use `requests.get(url, timeout=N)` to fetch raw XML first, then pass the string to `feedparser.parse(raw_content)`. feedparser explicitly supports parsing raw strings. This also gives control over User-Agent headers.

## 2026-03-26: Cloudflare blocks feedparser's default User-Agent — use a browser UA for RSS feeds
feedparser sends `feedparser/6.x.x +https://github.com/...` as its User-Agent, which Cloudflare classifies as a bot and returns 403 with `cf-mitigated: challenge`. Set a browser-like User-Agent string on all RSS feed requests.

## 2026-07-14: A uv-managed venv does not survive a laptop migration — check the interpreter, not just activate
When the machine changed, the pipeline broke silently. The `.venv/bin/activate` script was still present, so the old shell guard (`[[ -f "$VENV" ]]`) passed, but `.venv/bin/python` was a symlink into `~/.local/share/uv/python/cpython-3.13-macos-aarch64-none/` which no longer existed on the new host. The venv must be rebuilt (`uv venv && uv pip install -e '.[dev,markets]'`). The wrapper script now tests that the interpreter actually runs (`"$VENV_PY" --version`), not just that activate exists. Also: launchd agents live in `~/Library/LaunchAgents/` and are NOT part of the repo, so they must be re-registered (`launchctl bootstrap gui/$UID ...`) on a new machine. Keychain secrets (Gmail app password under service `morning-report-gmail`) and any `~/.zshenv` env vars (the old OpenWeatherMap key) also do not migrate.

## 2026-07-14: Prefer keyless data sources for unattended pipelines — switched weather to Open-Meteo
The OpenWeatherMap key lived only in `~/.zshenv` and was lost in the laptop migration, silently disabling the weather section. Replaced OpenWeatherMap with Open-Meteo (free, no API key). The gatherer now resolves locations to coordinates via `_KNOWN_COORDS` and maps WMO weather codes to the same English description strings the `weather_fr` filter already knows, so no template/generator change was needed. Removing the secret means this section can never break on a future migration. General rule: for anything running unattended, prefer a keyless source over one whose secret has to be re-provisioned per machine.

## 2026-07-26: `claude -p` cannot refresh its OAuth token from launchd — use `claude setup-token` for unattended runs
The scheduled 05:00 job worked for a week and then failed every morning with `Failed to authenticate: OAuth session expired and could not be refreshed`. The failure took 16ms, far too fast for any network round trip, so no refresh was being attempted. I ruled out the obvious causes with evidence rather than assumption: the gatherers had completed live HTTPS calls seven seconds earlier on the same run, so the network was up; the login keychain is `no-timeout` and I confirmed read, write and a live `claude -p` call all succeed from inside a real launchd job; no stale `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` existed anywhere; and the CLI version had not changed across the break. What remained is that the interactive OAuth access token lasts about 7.5 hours and the refresh path does not work from a launchd context, so whether the job succeeded depended entirely on how late Claude Code had been used the previous evening. The fix is `claude setup-token`, which issues a long-lived token with no refresh step, stored in the Keychain and exported as `CLAUDE_CODE_OAUTH_TOKEN`. General rule: an unattended job must not depend on a credential whose renewal needs an interactive session.

## 2026-07-26: A DNS lookup is not a connectivity check
The wrapper waited for the network with `until host api.anthropic.com`. On 22 July that check passed immediately and then every single fetch in the run failed with `NameResolutionError`, because a resolver can answer from cache while the interface is still associating. Probe with a real request (`curl -s --max-time 5 https://...`) instead. The same loop also measured its wait by counting its own `sleep` calls, so when the probe itself blocked for minutes the reported figure was meaningless and the real wait ran to 436s against a nominal 120s limit. Time a wait loop against the wall clock, never against a count of sleeps.

## 2026-07-26: Put the failure reason where the log will show it
Every failed run logged `claude CLI exited with code 1: (no stderr)`, which says nothing. The CLI writes its JSON envelope to stdout even when it fails and leaves stderr empty, so the real message ("Failed to authenticate...") was sitting in the envelope's `result` field the whole time and four mornings of logs were unreadable as a result. When wrapping a subprocess, check where that specific tool actually puts its errors rather than assuming stderr.
