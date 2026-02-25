# Morning Report System — Handoff Document

> **Context:** This document was generated from a claude.ai chat session on 2025-02-25.
> It captures all intelligence gathered and architectural decisions discussed.
> Read this into Claude Code in plan mode to bootstrap the repo.

---

## 1. What We're Building

A **daily morning briefing system** that aggregates information from multiple sources (Slack, Linear, Jira, email, meeting transcripts, calendar) and produces a structured morning report with:

- Summary of overnight activity across all channels
- Items requiring response or action
- Draft responses ready for review
- Sprint/project status updates
- Upcoming meetings and prep needed
- Travel/logistics reminders

The system should be runnable as a CLI tool or scheduled job, producing a markdown report (and optionally sending a summary to Slack or email).

---

## 2. The User

- **Steve Longmore** — Professor of Astrophysics at LJMU, co-founder of BolgiaTen (shipping intelligence), researcher for Allora Network, co-founder of Conservation AI
- Works across multiple time zones, travels internationally
- Uses Mac (macOS), Claude Code extensively, tmux for session management
- Prefers clean, well-structured solutions with clear documentation
- Has Claude Max subscription

---

## 3. Current Tool Ecosystem & Integrations

### Available via claude.ai MCP connectors (proven working)
| Service | Status | Notes |
|---------|--------|-------|
| **Slack** (BolgiaTen) | ✅ Connected | Single workspace only. User ID: U09RTDE4ZNF |
| **Linear** | ✅ Connected | Allora research tickets |
| **Jira** (Atlassian) | ✅ Connected | BolgiaTen EO-VT1 project |
| **Confluence** | ✅ Connected | Via Atlassian connector |
| **Fireflies** | ✅ Connected | Meeting transcripts |
| **Gmail** | ✅ Connected | Google accounts only |
| **Google Calendar** | ✅ Connected | |

### Not yet connected but needed
| Service | Solution | Notes |
|---------|----------|-------|
| **Apple Mail** (unified inbox) | MCP server | See §4 below — this is the primary gap |
| **Microsoft email accounts** | Via Apple Mail MCP | Multiple Microsoft accounts aggregated in Mac Mail |
| **Other Slack workspaces** | Not currently possible | Limited to one workspace per connector |

### Key limitation
The claude.ai chat interface has the MCP connectors but cannot access the local filesystem or git. Claude Code has filesystem/git but no MCP connectors. There is no teleport path from chat → Claude Code (open feature request: anthropics/claude-code#23017). This repo should bridge that gap by creating a local tool that can gather and cache data.

---

## 4. Apple Mail MCP Integration

Steve uses Mac Mail as a unified aggregator for several Microsoft, several Google, and other email accounts. This is the **highest-priority integration** since no single cloud connector covers all accounts.

### Community MCP servers (evaluated, not yet tested)

1. **sweetrb/apple-mail-mcp** (https://github.com/sweetrb/apple-mail-mcp)
   - Node.js, AppleScript bridge
   - Can install as Claude Code plugin: `/plugin marketplace add sweetrb/apple-mail-mcp`
   - Read, search, send, manage across all accounts
   - Most mature option

2. **patrickfreyer/apple-mail-mcp** (https://github.com/patrickfreyer/apple-mail-mcp)
   - Python-based, AppleScript bridge
   - Has .mcpb bundle for one-click Claude Desktop install
   - Supports account-specific sending
   - ENV var for user preferences

3. **lionsr/mcp-apple** (via LobeHub)
   - Node.js/Bun, uses JXA (JavaScript for Automation) — no string parsing
   - Clean type-safe approach
   - Broader Apple integration (not just Mail)

4. **pl-lyfx/apple-mail-mcp** (https://github.com/pl-lyfx/apple-mail-mcp)
   - Reads directly from local .emlx database files
   - Bypasses Mail.app AppleScript entirely
   - Claims better reliability
   - Most privacy-preserving (no app automation permissions needed)

### Recommendation
Evaluate sweetrb (most features) and pl-lyfx (most reliable) first. Both run locally — all data stays on the machine.

### Security consideration
These are community projects. Before granting Mail.app automation or Full Disk Access permissions, review the source code. Pin to a specific commit rather than tracking latest.

---

## 5. BolgiaTen Slack Workspace — Current State

### Channels
| Channel | ID | Purpose |
|---------|-----|---------|
| #all-bolgiaten | C09RZQTSBMY | Main team announcements, sprint updates |
| #dev-team | C0A8A1G3FKP | Development discussions, branching, tooling |
| #useful | C09S3J1P5TN | Links, articles, industry news |

### Team members
| Name | Slack ID | Role |
|------|----------|------|
| Steve Longmore | U09RTDE4ZNF | Co-founder, technical lead |
| Cormac Purcell | U09RZQT5T0S | Co-founder |
| Jonny | U09RJBWJFQX | Developer (EO-VT1) |
| Dan Walker | U09S3CF8LAG | Developer |
| Lior | (check) | Project/sprint manager |
| Steve Bowker | U0AFVQU359P | Team member (recently joined) |

### Active DM threads (as of 2025-02-25)
- **Steve ↔ Jonny** (D09RJBWQD2B): Dev workflow, Terraform decision tracking, Claude Code setup
- **Steve ↔ Cormac** (D09RZR8PMQA): March trip logistics (hotel, hire car, ferry), Claude Code skills

### Current action items from Slack (2025-02-25)
1. **Lior** wants Steve to collaborate on Sprint 3 tasks before Monday's kickstart
2. **Terraform decision** needs documenting — possible Claude hallucination between conversation contexts led to undocumented architectural choice (Jonny raised this)
3. **Dan Walker** flagged missing Claude Code skills in the guide: `/graduate-lessons`, `/write-handoff`, `/conversation-search`
4. **Backbone** Jira sync set up between BolgiaTen and LLI — tickets labelled "LLI" now sync
5. **March trip** — hotel and hire car still need booking (Steve & Cormac covering costs themselves)
6. **Sprint 2** — Lior asking team to review Jira tasks and 👍 to start sprint
7. **Weekly Wednesday standup** starting March 4th (end of Sprint 2)

---

## 6. Architecture Considerations

### Option A: Standalone CLI tool
- Python or Node.js script that calls various APIs/MCP servers
- Caches results locally in markdown/JSON
- Generates a morning report markdown file
- Can be run manually or via cron/launchd
- **Pro:** Simple, no dependencies beyond API keys
- **Con:** Duplicates connector logic that already exists in MCP

### Option B: MCP-native approach
- Build as an MCP server itself that orchestrates other MCP servers
- Could be used from Claude Desktop, Cowork, or Claude Code
- **Pro:** Composable, reusable
- **Con:** More complex, MCP orchestration patterns still maturing

### Option C: Hybrid — data gathering script + CLAUDE.md integration
- Script gathers and caches raw data from all sources
- Stores structured output in the repo (e.g., `briefings/2025-02-25.md`)
- Claude Code session starts by reading the cached briefing
- Claude then helps with responses, prioritisation, drafting
- **Pro:** Separation of concerns, works with existing tools
- **Con:** Two-step process

### Recommended: Start with Option C
Simplest path to value. The data gathering can be incrementally improved. The key insight is that the *intelligence gathering* happens via APIs/MCP, but the *response drafting and prioritisation* benefits from Claude's reasoning — and that part happens in Claude Code or chat.

---

## 7. Suggested Repo Structure

```
morning-report/
├── README.md
├── CLAUDE.md                    # Claude Code project instructions
├── pyproject.toml               # or package.json
├── src/
│   ├── gatherers/               # Data collection modules
│   │   ├── slack_gatherer.py    # Slack API integration
│   │   ├── email_gatherer.py    # Apple Mail MCP or direct
│   │   ├── linear_gatherer.py   # Linear API
│   │   ├── jira_gatherer.py     # Jira/Atlassian API
│   │   ├── calendar_gatherer.py # Google Calendar
│   │   └── fireflies_gatherer.py# Meeting transcripts
│   ├── report/
│   │   ├── generator.py         # Assembles report from gathered data
│   │   └── templates/           # Report templates (markdown)
│   └── cli.py                   # CLI entry point
├── config/
│   ├── config.yaml              # API keys, workspace IDs, preferences
│   └── config.example.yaml
├── briefings/                   # Generated reports (gitignored or separate)
│   └── 2025-02-25.md
└── tests/
```

---

## 8. Key Design Decisions to Make

1. **Language:** Python (Steve's research stack, good API libraries) vs Node.js (MCP servers are typically JS/TS)?
2. **Apple Mail approach:** Which MCP server to adopt, or build a lightweight custom one?
3. **Authentication:** How to handle API keys for Slack, Linear, Jira, Google — config file, env vars, keychain?
4. **Report format:** Pure markdown? Or structured JSON with a markdown renderer?
5. **Scheduling:** Manual CLI invocation first, then launchd/cron later?
6. **Scope of "response drafting":** Does the tool just gather and summarise, or does it also use Claude API to draft responses?

---

## 9. Immediate Next Steps

1. Create the repo with basic structure
2. Set up the Apple Mail MCP server (evaluate sweetrb and pl-lyfx)
3. Build the Slack gatherer first (API is well-understood, workspace is mapped)
4. Build the email gatherer (highest user need)
5. Generate first morning report from real data
6. Iterate: add Linear, Jira, Calendar, Fireflies gatherers
7. Add response drafting capability

---

## 10. Reference: Product Landscape (as of 2025-02-25)

- **claude.ai chat**: Has MCP connectors (Slack, Linear, Jira, Gmail, etc.), web search, file creation. No local filesystem or git access. No teleport to Claude Code.
- **Claude Code CLI**: Local filesystem, git, session resume/teleport. No MCP connectors.
- **Claude Code on web** (claude.ai/code): Like CLI but runs on Anthropic cloud. Teleportable to CLI. Needs GitHub connection.
- **Cowork**: Desktop tool, local filesystem access, MCP connectors via Claude Desktop config. Still in research preview. Available on Mac and Windows for Max/Team/Enterprise plans.
- **Connectors available in Cowork** (as of 2025-02-25): Google Drive, Google Calendar, Gmail, DocuSign, Apollo, Clay, Outreach, SimilarWeb, MSCI, LegalZoom, FactSet, WordPress, Harvey. No Apple Mail. No Outlook/Microsoft 365.
