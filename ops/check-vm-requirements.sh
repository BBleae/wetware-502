#!/usr/bin/env bash
# Verify that a VM meets the WETWARE-502 node requirements.
# Run INSIDE the target VM with sudo.
set -uo pipefail
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m %s\n' "$1"; }
bad(){ FAIL=$((FAIL+1)); printf '  \033[31mFAIL\033[0m %s\n' "$1"; }
have(){ command -v "$1" >/dev/null 2>&1; }

echo "[check] OS / kernel"
. /etc/os-release 2>/dev/null || true
[ "${ID:-}" = "ubuntu" ] && [ "${VERSION_ID:-}" = "22.04" ] && ok "Ubuntu 22.04" || bad "Ubuntu 22.04 (got ${PRETTY_NAME:-unknown})"
[ -d /run/systemd/system ] && ok "systemd is PID 1" || bad "systemd not found"
uname -r | grep -q generic && ok "generic kernel $(uname -r)" || bad "unexpected kernel $(uname -r)"

echo "[check] required commands"
for c in sshd nginx python3 gcc chattr mknod nft curl systemctl; do
  have "$c" && ok "$c" || bad "$c missing"
done

echo "[check] AppArmor"
if [ -d /sys/kernel/security/apparmor ]; then
  grep -q apparmor /sys/kernel/security/lsm 2>/dev/null && ok "AppArmor LSM active" || bad "AppArmor not in active LSM list"
else
  bad "AppArmor securityfs missing"
fi

echo "[check] mount namespaces"
unshare -m true 2>/dev/null && ok "unshare(CLONE_NEWNS) permitted" || bad "mount namespaces blocked (need CAP_SYS_ADMIN / privileged VM)"

echo "[check] immutable files on ext4"
mkdir -p /run/cortex-check && printf 'x' > /run/cortex-check/f
if chattr +i /run/cortex-check/f 2>/dev/null; then
  ok "chattr +i works on /run"
  chattr -i /run/cortex-check/f 2>/dev/null
else
  bad "chattr +i unsupported (use an ext4 bind mount for /run/cortex)"
fi
rm -rf /run/cortex-check

echo "[check] nftables"
nft list ruleset >/dev/null 2>&1 && ok "nftables readable" || bad "nftables unavailable"

echo "[check] listening ports"
ss -tln 2>/dev/null | grep -q ':2222 ' && ok "2222 listening" || bad "2222 not listening"
ss -tln 2>/dev/null | grep -q ':80 ' && ok "80 listening" || bad "80 not listening"

echo "[check] device node creation"
mknod /tmp/wetware-probe c 240 0 2>/dev/null && ok "mknod works" && rm -f /tmp/wetware-probe || bad "mknod blocked"

echo
echo "[check] $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
