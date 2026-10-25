#!/usr/bin/env bash
HERE="$(cd "$(dirname "$0")" && pwd)"; . "$HERE/config.sh"
# Reset story state and rebuild the real world files (no VM reboot).
set -euo pipefail
VM="${VM:-$WETWARE_VM}"
ssh "$VM" "sudo -n /usr/local/lib/cortex-agent/venv/bin/python /usr/local/lib/cortex-agent/reset.py --keep-images && sudo -n systemctl restart cortex-node-agent.service"
echo "[wetware] reset complete"
