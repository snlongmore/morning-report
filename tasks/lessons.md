# Lessons — Morning Report (Project-Specific)

## 2026-02-25: AppleScript `inbox of account` is unreliable — use unified inbox
Apple Mail's AppleScript `inbox of acct` property fails with `-1728` on some account types (Exchange, certain IMAP). The application-level `inbox` (unified inbox) works for all accounts. Per-account grouping can still be achieved by reading `name of account of mailbox of msg` on each message.

## 2026-02-25: AppleScript message body extraction causes timeouts — skip it
Fetching `content of msg` in AppleScript for even a small number of unread messages causes 60s+ timeouts on the unified inbox. Subject + sender is sufficient for morning triage; detailed content analysis belongs in the Claude skill layer, not the raw gatherer.

## 2026-02-25: AppleScript Calendar is unusably slow — use Swift/EventKit
AppleScript's `every event of cal whose start date >= today` iterates ALL events (including historical recurring events), causing AppleEvent timeouts (`-1712`) on calendars with any significant history. Swift/EventKit queries the CalendarKit database directly with proper date-range predicates and returns results instantly. Always prefer EventKit for macOS calendar access.

## 2026-02-25: EventKit requires explicit permission grant on first run
The Swift calendar helper prompts for calendar access permission on first run. This is a one-time macOS permission grant. If it fails silently, check System Settings > Privacy & Security > Calendars.
