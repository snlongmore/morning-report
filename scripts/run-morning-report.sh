#!/bin/bash
# Morning Report — daily automation wrapper for launchd
# Sources environment variables and runs the full pipeline.

set -euo pipefail

# Source environment (API keys, GMAIL_APP_PASSWORD)
if [[ -f "$HOME/.zshenv" ]]; then
    source "$HOME/.zshenv"
fi

# Activate the project virtual environment
VENV="/Users/stevenlongmore/GitHub_repos/snl/morning_report/.venv/bin/activate"
if [[ -f "$VENV" ]]; then
    source "$VENV"
else
    echo "ERROR: Virtual environment not found at $VENV" >&2
    exit 1
fi

# Run the full pipeline
echo "$(date '+%Y-%m-%d %H:%M:%S') — Starting morning report"
morning-report auto 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') — Morning report complete"
