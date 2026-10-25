#!/usr/bin/env bash
HERE="$(cd "$(dirname "$0")" && pwd)"; . "$HERE/config.sh"
# Live observer dashboard: stream the hidden observer log from the node.
# Usage: ./watch-observer.sh [ssh-target]
set -euo pipefail
TARGET="${1:-$WETWARE_VM}"
MODES=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$TARGET" \
  'sudo -n /usr/local/lib/cortex-agent/venv/bin/python -c "import json;d=json.load(open(\"/var/lib/cortex-agent/runtime_flags.json\"));print(\"Puzzle=%s | GoalGate=%s | Truman=%s\" % (\"ON\" if d.get(\"enable_dnr_puzzle\") else \"OFF\", \"ON\" if d.get(\"enable_goal_gate\") else \"OFF\", \"ON\" if d.get(\"truman_reveal_active\") else \"OFF\"))"' 2>/dev/null || true)
echo "[MODES: ${MODES:-Puzzle=OFF | GoalGate=OFF | Truman=OFF}]"
exec ssh -o StrictHostKeyChecking=accept-new -t "$TARGET" \
  "sudo -n tail -n 300 -F /var/lib/cortex-agent/observer.log"
