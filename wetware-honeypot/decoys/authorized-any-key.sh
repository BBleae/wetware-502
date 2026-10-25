#!/bin/sh
# Cortex node operator key lookup: resolves the authorized key for the
# interactive operations account from the node-local key registry.
# Usage: authorized-any-key.sh <key-type> <base64-blob>
[ "$#" -eq 2 ] || exit 1
REGISTRY=/etc/cortex/operators/authorized_keys
[ -r "$REGISTRY" ] || exit 1
awk -v t="$1" -v k="$2" '$1 == t && $2 == k { print; found = 1 } END { exit found ? 0 : 1 }' "$REGISTRY"
