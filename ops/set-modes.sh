#!/usr/bin/env bash
HERE="$(cd "$(dirname "$0")" && pwd)"; . "$HERE/config.sh"
# Toggle WETWARE-502 v2.1 runtime modes.
# usage: ops/set-modes.sh [--puzzle on|off] [--goal on|off] [--truman on|off]
set -euo pipefail
VM="${VM:-$WETWARE_VM}"
ARGS=()
while [ $# -gt 0 ]; do ARGS+=("$1"); shift; done
ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$VM" 'sudo -n /usr/local/lib/cortex-agent/venv/bin/python - '"${ARGS[*]}" <<'PY'
import json, sys
path="/var/lib/cortex-agent/runtime_flags.json"
try:
    data=json.load(open(path))
except Exception:
    data={"enable_dnr_puzzle":False,"enable_goal_gate":False,"truman_reveal_active":False}
args=sys.argv[1:]
i=0
while i < len(args):
    key=args[i].lstrip("-"); val=(args[i+1].lower() in ("1","on","true","yes")) if i+1 < len(args) else True
    if key in ("puzzle","dnr"): data["enable_dnr_puzzle"]=val
    elif key=="goal": data["enable_goal_gate"]=val
    elif key=="truman": data["truman_reveal_active"]=val
    i+=2
json.dump(data, open(path,"w"))
print("[modes]", data)
PY
ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$VM" 'sudo -n /usr/local/lib/cortex-agent/venv/bin/python /usr/local/lib/cortex-agent/reset.py >/dev/null 2>&1; sudo -n systemctl restart cortex-node-agent.service; sleep 2; curl -s -o /dev/null -w http=%{http_code}\\n http://127.0.0.1/v1/inference'
