#!/usr/bin/env bash
# Install the WETWARE-502 story engine into the real-systemd host container.
# Run as root on the VM.  The container rootfs must already be mounted by
# wetware-host-prod-cortex-04.mount; the container itself is managed by
# systemd-nspawn as machine "prod-cortex".
set -euo pipefail

ROOT=${ROOT:-/var/lib/wetware-hosts/prod-cortex-04}
MACHINE=${MACHINE:-prod-cortex}
ENGINE=${ENGINE:-/usr/local/lib/cortex-agent}
PAYLOAD=${PAYLOAD:-$ENGINE/engine-src}
HOST_ID=${HOST_ID:-prod-cortex-04}

[ -d "$ROOT/etc" ] || { echo "container rootfs not mounted: $ROOT" >&2; exit 2; }
[ -d "$PAYLOAD" ] || { echo "engine payload missing: $PAYLOAD" >&2; exit 2; }
command -v systemd-run >/dev/null || { echo "systemd-run missing" >&2; exit 2; }

echo "[engine] installing code from $PAYLOAD"
mkdir -p "$ROOT$ENGINE"
tar -C "$PAYLOAD" -czf - --exclude '__pycache__' --exclude 'tests' . |
  tar -xzpf - -C "$ROOT$ENGINE"

echo "[engine] compiling container login shell"
cc -O2 -Wall -o /tmp/cortex-shell-container ops/nspawn/container_shell.c 2>/dev/null ||
  cc -O2 -Wall -o /tmp/cortex-shell-container -x c - <<'EOF'
#include <unistd.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    char **a; int i;
    setenv("PYTHONPATH", "/usr/local/lib/cortex-agent", 1);
    a = calloc((size_t)argc + 3, sizeof(char *));
    if (!a) return 127;
    a[0] = "/usr/bin/python3"; a[1] = "-c";
    a[2] = "import sys,os;sys.path.insert(0,os.environ.get('PYTHONPATH',''));import console_core;sys.exit(console_core.main())";
    for (i = 1; i < argc; i++) a[i + 2] = argv[i];
    a[argc + 2] = NULL;
    execv("/usr/bin/python3", a); return 127;
}
EOF
install -m 0755 /tmp/cortex-shell-container "$ROOT/usr/local/bin/cortex-shell"
grep -qx /usr/local/bin/cortex-shell "$ROOT/etc/shells" 2>/dev/null ||
  echo /usr/local/bin/cortex-shell >> "$ROOT/etc/shells"
chroot "$ROOT" usermod -s /usr/local/bin/cortex-shell root
chroot "$ROOT" chpasswd <<'EOF'
root:123456
EOF

echo "[engine] configuring guest sshd"
mkdir -p "$ROOT/etc/ssh/sshd_config.d" "$ROOT/var/lib/cortex-agent" "$ROOT/var/log/cortex"
cat > "$ROOT/etc/ssh/sshd_config.d/99-wetware.conf" <<'EOF'
PermitRootLogin yes
PasswordAuthentication yes
KbdInteractiveAuthentication yes
UsePAM yes
PrintMotd no
EOF
chroot "$ROOT" systemctl enable ssh >/dev/null 2>&1 || true

echo "[engine] configuring guest network"
cat > "$ROOT/etc/systemd/network/20-wetware-host0.network" <<'EOF'
[Match]
Name=host0

[Network]
Address=10.66.0.4/24
Gateway=10.66.0.1
DNS=8.8.8.8
LinkLocalAddressing=no
IPv6AcceptRA=no
ConfigureWithoutCarrier=yes
EOF
rm -f "$ROOT/etc/systemd/network/70-wetware-prod-cortex.network"

echo "[engine] materialising the story world inside the machine"
systemd-run -M "$MACHINE" --wait --pipe --quiet /bin/sh -c \
  "cd $ENGINE && PYTHONPATH=$ENGINE WETWARE_STATE_DIR=/var/lib/cortex-agent /usr/bin/python3 reset.py" || true

echo "[engine] installing real HTTP upstream + nginx surface"
cat > "$ROOT/etc/systemd/system/wetware-upstream.service" <<'EOF'
[Unit]
Description=wetware inference upstream
After=network.target

[Service]
ExecStart=/usr/bin/python3 /usr/local/lib/cortex-agent/pod_http.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF
mkdir -p "$ROOT/etc/nginx/conf.d"
# The vendor vhost in conf.d is a named server (story artifact) and the only
# default_server is the runtime drop-in below.  Do not delete the vendor config:
# an operator inspecting the node must still find it on disk.
cat > "$ROOT/etc/nginx/conf.d/00-wetware.conf" <<'EOF'
server {
  listen 80 default_server;
  listen [::]:80 default_server;
  access_log /var/log/nginx/access.log;
  error_log /var/log/nginx/error.log;
  location / { proxy_pass http://127.0.0.1:8000; }
}
EOF
systemd-run -M "$MACHINE" --wait --pipe --quiet /bin/sh -c \
  "systemctl daemon-reload; systemctl enable --now wetware-upstream.service; nginx -t && systemctl restart nginx" || true

echo "[engine] installing the real PID 4040 worker unit"
mkdir -p "$ROOT/opt/cortex/bin"
systemctl -M "$MACHINE" stop cortex-api.service 2>/dev/null || true
[ -e "$ROOT/opt/cortex/bin/synapse_worker" ] && chattr -i "$ROOT/opt/cortex/bin/synapse_worker" 2>/dev/null || true
if [ -x /usr/local/lib/cortex-agent/pod/worker ]; then
  install -m 0755 /usr/local/lib/cortex-agent/pod/worker "$ROOT/opt/cortex/bin/synapse_worker"
else
  cc -O2 -o "$ROOT/opt/cortex/bin/synapse_worker" -x c - <<'CEOF'
#include <sys/prctl.h>
#include <unistd.h>
int main(int argc, char **argv) {
    if (argc > 1) prctl(PR_SET_NAME, argv[1], 0, 0, 0);
    for (;;) sleep(3600);
    return 0;
}
CEOF
fi
truncate -s 8492104 "$ROOT/opt/cortex/bin/synapse_worker"
chmod 0755 "$ROOT/opt/cortex/bin/synapse_worker"
chattr +i "$ROOT/opt/cortex/bin/synapse_worker" 2>/dev/null || true
cat > "$ROOT/etc/systemd/system/cortex-api.service" <<'SEOF'
[Unit]
Description=Cortex API inference worker (node 04)
After=network.target

[Service]
Type=simple
ExecStartPre=/bin/mount -o remount,rw /proc/sys
ExecStartPre=/bin/sh -c "echo 4039 > /proc/sys/kernel/ns_last_pid"
# vendor recovery hook: clears the thalamic lock before the worker is respawned
ExecStartPre=-/opt/cortex/bin/resuscitate.sh --unanesthetized --quiet
ExecStart=/opt/cortex/bin/synapse_worker synapse_worker --mode=production --bind-cortex=/dev/wetware0
Restart=no

[Install]
WantedBy=multi-user.target
SEOF
systemd-run -M "$MACHINE" --wait --pipe --quiet /bin/sh -c \
  "systemctl daemon-reload; systemctl enable cortex-api.service; systemctl restart cortex-api.service; sleep 0.3; systemctl show -p MainPID --value cortex-api.service" || true

echo "[engine] installing boot-safe nginx config"
cat > "$ROOT/usr/local/lib/cortex-agent/fix_nginx.sh" <<'FIX'
#!/bin/sh
# Boot guard: keep exactly one default_server (the runtime drop-in) and leave
# the vendor vhost and site files untouched so the node's own records survive a
# restart.  nginx.conf includes conf.d only, never sites-enabled.
mkdir -p /etc/nginx/conf.d
cat > /etc/nginx/conf.d/00-wetware.conf <<'NGX'
server {
  listen 80 default_server;
  listen [::]:80 default_server;
  access_log /var/log/nginx/access.log;
  error_log /var/log/nginx/error.log;
  location / { proxy_pass http://127.0.0.1:8000; }
}
NGX
exit 0
FIX
chmod 755 "$ROOT/usr/local/lib/cortex-agent/fix_nginx.sh"
mkdir -p "$ROOT/etc/systemd/system/nginx.service.d"
cat > "$ROOT/etc/systemd/system/nginx.service.d/wetware.conf" <<'UNIT'
[Service]
ExecStartPre=/usr/local/lib/cortex-agent/fix_nginx.sh
UNIT
systemd-run -M "$MACHINE" --wait --pipe --quiet /bin/sh -c "/usr/local/lib/cortex-agent/fix_nginx.sh; systemctl daemon-reload; systemctl restart nginx" || true

echo "[engine] installing host<->container network guard"
cat > /usr/local/sbin/wetware-net-guard.sh <<'NET'
#!/bin/sh
# The distro ruleset loaded by nftables.service drops RFC1918 output, which
# silently cuts the container veth.  Re-apply the host plumbing on every boot.
nft list table ip nat >/dev/null 2>&1 || nft add table ip nat
nft list chain ip nat post >/dev/null 2>&1 || \
  nft add chain ip nat post '{ type nat hook postrouting priority 100; policy accept; }'
nft list chain ip nat post 2>/dev/null | grep -q '10.66.0.0/24' || \
  nft add rule ip nat post ip saddr 10.66.0.0/24 masquerade
nft list chain inet filter forward 2>/dev/null | grep -q 've-prod-cortex' || {
  nft add rule inet filter forward iifname "ve-prod-cortex" accept
  nft add rule inet filter forward oifname "ve-prod-cortex" accept
}
nft list chain inet filter output 2>/dev/null | grep -q '10.66.0.0/24 accept' || \
  nft insert rule inet filter output ip daddr 10.66.0.0/24 accept
sysctl -q -w net.ipv4.ip_forward=1 || true
exit 0
NET
chmod 755 /usr/local/sbin/wetware-net-guard.sh
cat > /etc/sysctl.d/99-wetware-forward.conf <<'SYS'
net.ipv4.ip_forward=1
SYS
cat > /etc/systemd/system/wetware-net-guard.service <<'UNIT'
[Unit]
Description=WETWARE host/container network guard (veth forward, output allow, NAT)
After=nftables.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/wetware-net-guard.sh

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now wetware-net-guard.service >/dev/null 2>&1 || true
/usr/local/sbin/wetware-net-guard.sh || true

echo "[engine] done"
