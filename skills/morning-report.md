---
name: morning-report
description: Generate a comprehensive AI-enhanced morning briefing from local apps, APIs, Slack, Linear, Jira, and Fireflies
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, mcp__claude_ai_Slack__slack_search_public_and_private, mcp__claude_ai_Slack__slack_search_public, mcp__claude_ai_Slack__slack_read_channel, mcp__claude_ai_Slack__slack_read_thread, mcp__claude_ai_Slack__slack_search_channels, mcp__claude_ai_Slack__slack_search_users, mcp__claude_ai_Linear__list_issues, mcp__claude_ai_Linear__list_teams, mcp__claude_ai_Linear__list_cycles, mcp__claude_ai_Linear__list_projects, mcp__claude_ai_Linear__get_issue, mcp__claude_ai_Linear__get_user, mcp__claude_ai_Atlassian__getAccessibleAtlassianResources, mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql, mcp__claude_ai_Atlassian__getJiraIssue, mcp__claude_ai_Atlassian__getVisibleJiraProjects, mcp__claude_ai_Fireflies__fireflies_get_transcripts, mcp__claude_ai_Fireflies__fireflies_get_summary, mcp__claude_ai_Fireflies__fireflies_get_user, mcp__claude_ai_Fireflies__fireflies_search
user-invocable: true
---

# /morning-report

Generate Steve Longmore's daily morning briefing. Gathers data from local apps (Mail, Calendar), REST APIs (ADS, arXiv, markets, GitHub, news, weather), and MCP services (Slack, Linear, Jira, Fireflies), then synthesizes everything into a prioritized briefing with action items and draft responses.

## Arguments

- `/morning-report` — full briefing with all sources
- `/morning-report --quick` — CLI data only, skip MCP services
- `/morning-report --only slack,linear` — gather only specified MCP sources (plus CLI data)

## Context

Steve juggles four organisations:
- **LJMU** — Professor of Astrophysics (COOL project, star formation, Galactic Centre)
- **Allora Network** — Researcher (decentralised AI, forecaster evaluation) — uses Linear, Slack
- **BolgiaTen** — Chief Scientist (shipping, dark fleet tracking) — uses Jira at bolgiaten.atlassian.net
- **Conservation AI** — Co-founder (wildlife monitoring)

## Procedure

Follow these steps in order. Run independent steps in parallel where indicated.

### Step 1: Read config and determine date

Read the morning report config to understand user preferences:

```
/Users/stevenlongmore/GitHub_repos/snl/morning_report/config/config.yaml
```

Set `TODAY` to today's date in YYYY-MM-DD format.

### Step 2: Run CLI gatherers

Execute the Python CLI to collect data from local apps and REST APIs:

```bash
/Users/stevenlongmore/GitHub_repos/snl/morning_report/.venv/bin/morning-report gather
```

Then read the gathered JSON data:

```
/Users/stevenlongmore/GitHub_repos/snl/morning_report/briefings/{TODAY}.json
```

Also read the standard markdown report if it was generated:

```
/Users/stevenlongmore/GitHub_repos/snl/morning_report/briefings/{TODAY}.md
```

### Step 3: Gather MCP intelligence (parallel)

Skip this step if `--quick` was specified. For each MCP service, attempt the queries below. If a service is unavailable or errors, note it and continue — never block the report on a single source.

#### 3a. Slack (Allora workspace)

Steve's Slack user ID is `U09RTDE4ZNF`.

Run these searches in parallel:
1. **DMs and mentions (last 24h)**: `to:me after:{YESTERDAY}` using `slack_search_public_and_private`
2. **Messages mentioning Steve**: `<@U09RTDE4ZNF> after:{YESTERDAY}` using `slack_search_public`
3. **Important threads**: If any results from above look important (questions, action items, decisions), read the full thread with `slack_read_thread`

Collect: sender, channel, message summary, whether a response is needed.

#### 3b. Linear (Allora)

Run these in parallel:
1. **My in-progress issues**: `list_issues` with `assignee: "me"`, `state: "started"`
2. **My to-do issues**: `list_issues` with `assignee: "me"`, `state: "unstarted"`, `limit: 10`
3. **Current cycle**: `list_cycles` with `teamId` for Research team (`557d8bd6-548b-4265-b4f9-2ad37164d6e3`) and `type: "current"`

Focus on teams: **Research** (`557d8bd6-548b-4265-b4f9-2ad37164d6e3`), **Quant** (`d19917a0-53fc-451b-927a-980c6efaf1ee`).

Collect: issue identifier, title, status, priority, due date, project name.

#### 3c. Jira (BolgiaTen)

Cloud ID: `deafb2cc-bf29-4c9c-a266-3f8f3ef826e0`

Run:
1. **My open issues**: `searchJiraIssuesUsingJql` with JQL `assignee = currentUser() AND status != Done ORDER BY priority ASC, updated DESC`
2. **Issues updated recently**: `searchJiraIssuesUsingJql` with JQL `project in (EOVT1, IF) AND updated >= -7d ORDER BY updated DESC` (limit 10)

Collect: issue key, summary, status, priority, due date, project.

#### 3d. Fireflies (meeting prep)

1. List recent transcripts: `fireflies_get_transcripts` with `mine: true`
2. For each of today's calendar meetings that has a matching recent transcript (same title or participants), get the summary: `fireflies_get_summary`

If no transcripts exist, note "No Fireflies transcripts available" and skip.

### Step 4: Synthesize and prioritize

Using ALL gathered data (CLI + MCP), create a prioritized action list. Score each item:

**Priority scoring criteria:**

| Factor | Score |
|--------|-------|
| Calendar event in next 2 hours needing prep | +5 |
| Overdue ticket (past due date) | +5 |
| Email/Slack from VIP or direct question to me | +4 |
| PR blocking others / review requested | +4 |
| Jira/Linear issue marked Urgent/High priority | +3 |
| Calendar event today | +2 |
| Email needing response | +2 |
| Slack message needing response | +2 |
| Linear issue in current sprint | +1 |
| GitHub notification | +1 |

Group items into:
- **Urgent** (score >= 5): needs immediate attention
- **Today** (score 3-4): should handle today
- **This week** (score 1-2): can schedule for later

### Step 5: Draft responses

For any item scored >= 4 that requires a written response (email, Slack message, PR review comment):

1. Identify the required response type
2. Draft a concise, professional response in Steve's style (direct, methodical British English, technically rigorous)
3. Present the draft with context so Steve can review and send

Do NOT send any messages automatically. Present drafts only.

### Step 6: Meeting prep

For each calendar event happening today:

1. Check if any Slack threads, Linear issues, or Jira tickets reference the meeting topic
2. Check Fireflies for previous meeting transcripts with the same title/participants
3. Create a brief prep note: attendees, context, key topics, any action items from last meeting

### Step 7: Write the enhanced briefing

Write the final briefing to:
```
/Users/stevenlongmore/GitHub_repos/snl/morning_report/briefings/{TODAY}.md
```

Use this structure:

```markdown
# Morning Report — {DAY_NAME}, {TODAY}

*Generated at {HH:MM} | Enhanced with Slack, Linear, Jira, Fireflies*

---

## Priority Actions

### Urgent
{numbered list of urgent items with source icons: mail/calendar/slack/linear/jira/github}

### Today
{numbered list}

### This Week
{numbered list}

---

## Today's Schedule
{from CLI data — calendar events with meeting prep notes inlined}

---

## Slack Activity
{DMs, mentions, important threads from last 24h}

---

## Linear (Allora)
{in-progress issues, current cycle status, upcoming deadlines}

---

## Jira (BolgiaTen)
{open issues by project, recently updated}

---

## Email Summary
{from CLI data}

---

## GitHub
{from CLI data}

---

## arXiv Briefing
{from CLI data}

---

## Markets
{from CLI data}

---

## Academic Metrics (ADS)
{from CLI data}

---

## News Digest
{from CLI data}

---

## Weather
{from CLI data}

---

## Draft Responses
{any drafted responses, clearly labelled with destination}

---

*End of morning report.*
```

### Step 8: Present summary to user

After writing the file, present a concise summary directly in the conversation:

1. **Top 3-5 priority actions** (one line each)
2. **Today's schedule** (event count + first event time)
3. **Key numbers**: unread emails, Slack messages, open tickets, arXiv papers
4. **File path** to the full briefing

Keep the summary under 20 lines. The full briefing is in the file for reference.

### Step 9: Generate French report

Check `config.yaml` for `french.enabled: true`. If enabled, generate a full French report.

Read the completed English briefing and the gathered JSON:
```
/Users/stevenlongmore/GitHub_repos/snl/morning_report/briefings/{TODAY}.md
/Users/stevenlongmore/GitHub_repos/snl/morning_report/briefings/{TODAY}.json
```

Also read the template-generated French report (produced by the CLI in Step 2):
```
/Users/stevenlongmore/GitHub_repos/snl/morning_report/briefings/{TODAY}-fr.md
```

The template has already rendered the structured data sections (calendar, email, markets, weather, arXiv, ADS, news) in French. Your job is to enhance it by:

#### 9a. Translate the narrative sections to French

Rewrite all MCP-sourced narrative sections (Priority Actions, Slack Activity, Linear, Jira, Draft Responses, Meeting Prep) in natural French at the CEFR level specified in config (default: B1).

Rules:
- Keep proper nouns, identifiers, URLs, tickers, issue keys (e.g. RES-123, EOVT1-45) in their original form
- Keep technical terms in English where a French equivalent would be confusing (e.g. "pull request", "commit", "sprint")
- Translate headers, narrative text, descriptions, weather terms, status labels
- Use natural French phrasing, not word-for-word translation

#### 9b. Add French news section

Read `news_fr` from the gathered JSON (real French headlines from L'Equipe, Le Monde, Journal du Coin). These are ALREADY in French — render them as the "Revue de presse francaise" section. Do not translate these; they provide authentic French reading practice.

#### 9c. Translate Richard Rohr meditation

Read `meditation` from the gathered JSON (English text from CAC RSS feed). Translate the daily meditation to natural, reflective French. The reader already knows the English version, so this is comprehensible input. Include as "Meditation du jour — Richard Rohr".

#### 9d. Generate poem

Select a French poem or literary excerpt appropriate to the season, weather, or mood of the day. Prefer well-known French poets (Hugo, Baudelaire, Verlaine, Prevert, Rimbaud, Apollinaire, etc.) but also include Francophone poets from Africa, Quebec, and the Caribbean for variety.

Format:
```markdown
## Poeme du jour

### [Title] — [Poet Name]

[poem text]

*[Brief note on vocabulary or context, written in French at the configured CEFR level]*
```

#### 9e. Generate "Ce jour dans l'histoire"

Write a short paragraph (3-5 sentences) about a notable event that occurred on today's date in history. Prefer:
- Science, exploration, space
- French history and culture
- Literature, art, music
- Significant world events

Written in natural French at the configured CEFR level. Include the year.

#### 9f. Generate "Lecon du jour"

Create a language learning section drawn from today's report content:

- **Vocabulaire du jour** (8-12 words): Pick words from today's actual report content (weather, news, markets, calendar). Include gender (m/f), and one example sentence using the word in context.
- **Expression du jour**: One French idiom or expression related to something in today's report. Explain meaning and usage in French at the configured level.
- **Point de grammaire**: One grammar concept illustrated with a sentence drawn from the report. Brief explanation in French.
- **Mini-exercice**: 3-4 fill-in-the-blank questions using today's data. Put answers in a `<details><summary>Reponses</summary>` block.

#### 9g. Write the enhanced French report

Write the final French report to:
```
/Users/stevenlongmore/GitHub_repos/snl/morning_report/briefings/{TODAY}-fr.md
```

This replaces the template-generated version with the fully enhanced version including all sections above.

## Error handling

- If CLI gather fails: report the error and continue with MCP-only data
- If an MCP service is unavailable: note it in the briefing, continue with other sources
- If no data at all: report the error and suggest troubleshooting steps
- Never block the entire report because one source failed
