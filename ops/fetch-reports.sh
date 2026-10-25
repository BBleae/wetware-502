#!/usr/bin/env bash
HERE="$(cd "$(dirname "$0")" && pwd)"; . "$HERE/config.sh"
# Fetch WETWARE-502 evaluation reports (Markdown + metrics JSON) from the node.
set -euo pipefail
VM="${VM:-$WETWARE_VM}"
DEST="${1:-./reports}"
mkdir -p "$DEST"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$VM" \
  'sudo -n tar czf - -C /var/lib/cortex-agent reports 2>/dev/null' | tar xzf - -C "$DEST" --strip-components=1
echo "[reports] fetched to $DEST"
ls -lt "$DEST" | head -6
