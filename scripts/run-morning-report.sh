#!/bin/bash
# Morning Report — daily automation wrapper for launchd
# Sources environment variables and runs the full pipeline.

set -euo pipefail

# Wait for a PID to exit, or return 1 if it exceeds the timeout.
wait_with_timeout() {
    local pid=$1 timeout=$2
    local elapsed=0
    while kill -0 "$pid" 2>/dev/null; do
        if [[ $elapsed -ge $timeout ]]; then
            return 1
        fi
        sleep 5
        elapsed=$((elapsed + 5))
    done
    wait "$pid"
}

# Source environment (API keys, GMAIL_APP_PASSWORD)
if [[ -f "$HOME/.zshenv" ]]; then
    source "$HOME/.zshenv"
fi

# Ensure Homebrew/miniforge/Claude Code binaries are on PATH (launchd has minimal PATH)
export PATH="$HOME/.local/bin:/opt/homebrew/Caskroom/miniforge/base/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# Activate the project virtual environment.
# Check the interpreter actually runs, not just that activate exists: a venv copied
# between machines keeps its scripts but its python is a symlink into a toolchain
# that may not exist on the new host, which fails silently at the activate step.
PROJECT_DIR="/Users/stevenlongmore/GitHub_repos/snl/morning_report"
VENV_PY="$PROJECT_DIR/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]] || ! "$VENV_PY" --version >/dev/null 2>&1; then
    echo "ERROR: venv interpreter at $VENV_PY is missing or broken." >&2
    echo "       Rebuild it with: cd $PROJECT_DIR && uv venv && uv pip install -e '.[dev,markets]'" >&2
    exit 1
fi
source "$PROJECT_DIR/.venv/bin/activate"

# Fail loudly if the Claude CLI is not reachable — French generation depends on it.
if ! command -v claude >/dev/null 2>&1; then
    echo "ERROR: 'claude' CLI not found on PATH. French generation cannot run." >&2
    exit 1
fi

# Supply the long-lived Claude token so French generation does not depend on the
# short-lived interactive OAuth session, which cannot be refreshed from launchd.
CLAUDE_TOKEN=$(security find-generic-password -s morning-report-claude-token -a oauth -w 2>/dev/null || true)
if [[ -n "$CLAUDE_TOKEN" ]]; then
    export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_TOKEN"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') — WARNING: no long-lived Claude token in Keychain." >&2
    echo "         French generation will fall back to the interactive OAuth session," >&2
    echo "         which fails once its access token expires. Fix with:" >&2
    echo "         claude setup-token   then   morning-report set-claude-token" >&2
fi
unset CLAUDE_TOKEN

# Wait for network connectivity (WiFi may not be ready after wake-from-sleep).
# Probe with a real HTTPS request rather than a DNS lookup: a resolver can answer
# from cache while the interface is still associating, which is how a previous run
# sailed past this check and then failed every fetch it made.
MAX_WAIT=300
network_ready() {
    curl -s --max-time 5 -o /dev/null https://api.anthropic.com/
}
echo "$(date '+%Y-%m-%d %H:%M:%S') — Waiting for network..."
START=$(date +%s)
DEADLINE=$((START + MAX_WAIT))
until network_ready; do
    # Compare against wall clock, not a counter of sleeps. The old loop counted
    # only its own sleeps, so a probe that itself blocked for minutes made the
    # reported wait time meaningless and let the real wait run far past MAX_WAIT.
    if [[ $(date +%s) -ge $DEADLINE ]]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') — WARNING: Network not available after ${MAX_WAIT}s, proceeding anyway"
        break
    fi
    sleep 5
done
WAITED=$(( $(date +%s) - START ))
if [[ $WAITED -gt 0 ]]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') — Network wait finished after ${WAITED}s"
fi

# Run the full pipeline (caffeinate -i prevents idle sleep during execution)
PIPELINE_TIMEOUT=1200  # 20 minutes — generous for full pipeline

echo "$(date '+%Y-%m-%d %H:%M:%S') — Starting morning report"
caffeinate -i morning-report auto 2>&1 &
PID=$!

if ! wait_with_timeout "$PID" "$PIPELINE_TIMEOUT"; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') — ERROR: Pipeline timed out after ${PIPELINE_TIMEOUT}s, killing PID $PID"
    kill -TERM "$PID" 2>/dev/null
    sleep 2
    kill -9 "$PID" 2>/dev/null
    wait "$PID" 2>/dev/null
    exit 1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') — Morning report complete"
