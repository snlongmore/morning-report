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
