#!/usr/bin/env bash
# SessionStart hook. In Claude Code cloud sessions, make sure Blender is installed before work
# starts. Locally it only reports status (install yourself with `make setup`).
# Whatever this prints to stdout is added to Claude's context for the session.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "${CLAUDE_CODE_REMOTE:-}" == "true" ]]; then
  "$ROOT/scripts/setup.sh" --quiet 2>&1 | tail -5
else
  "$ROOT/scripts/setup.sh" --check 2>&1 | tail -1
fi
exit 0
