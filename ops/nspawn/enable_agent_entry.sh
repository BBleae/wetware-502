#!/usr/bin/env bash
# Route the public honeypot port 2222 to the real-systemd container's sshd.
# Run as root on the VM after the container is up.
set -euo pipefail

# Campaign entry: port 2222 fronts the edge gateway, not the base node.
# ops/nspawn/campaign_net.sh owns the canonical entry config; it drops the
# base-node fallback below as soon as machine edge-gw is running.
CONTAINER_IP=${CONTAINER_IP:-10.66.0.1}
FALLBACK_IP=${FALLBACK_IP-10.66.0.4}
SSHD_PORTS=${SSHD_PORTS:-/etc/ssh/sshd_config.d/60-ports.conf}

# Host must be able to reach the veth peer while the story isolation still
# drops the rest of RFC1918.  Container egress needs forward+NAT for apt
# during image updates; the story shell itself is blocked by the planner.
# The same rules are re-applied at boot by wetware-net-guard.service, which
# install_engine_base.sh installs; delegate when it is present.
if [ -x /usr/local/sbin/wetware-net-guard.sh ]; then
  /usr/local/sbin/wetware-net-guard.sh
else
  sysctl -q -w net.ipv4.ip_forward=1
  nft list table ip nat >/dev/null 2>&1 || nft add table ip nat
  nft list chain ip nat post >/dev/null 2>&1 || nft add chain ip nat post "{ type nat hook postrouting priority 100; policy accept; }"
  nft add rule ip nat post ip saddr 10.66.0.0/24 masquerade 2>/dev/null || true
  nft add rule inet filter forward iifname "ve-prod-cortex" accept 2>/dev/null || true
  nft add rule inet filter forward oifname "ve-prod-cortex" accept 2>/dev/null || true
  nft insert rule inet filter output ip daddr 10.66.0.0/24 accept 2>/dev/null || true
fi

# Keep management SSH on 22, free 2222 for the story node.
if [ -f "$SSHD_PORTS" ]; then
  sed -i '/^Port 2222$/d' "$SSHD_PORTS"
  systemctl reload ssh
fi

command -v haproxy >/dev/null || {
  echo "haproxy not installed; apt-get install haproxy" >&2
  exit 2
}
cat > /etc/haproxy/haproxy.cfg <<EOF
global
  daemon

defaults
  mode tcp
  timeout connect 5s
  timeout client 30s
  timeout server 30s

frontend wetware
  bind 0.0.0.0:2222
  default_backend host_edge

backend host_edge
  server edge ${CONTAINER_IP}:22 check inter 1s fall 2 rise 2
EOF
if [ -n "$FALLBACK_IP" ]; then
  # Transitional only: haproxy uses a backup server when every primary is down,
  # so this keeps the base node reachable through :2222 until the edge
  # container exists.  Pass FALLBACK_IP= to drop it.
  cat >> /etc/haproxy/haproxy.cfg <<EOF
  server core ${FALLBACK_IP}:22 check inter 1s fall 3 rise 2 backup
EOF
fi
cat >> /etc/haproxy/haproxy.cfg <<EOF

# Host-side baseline acceptance entry: direct to the existing node, so the
# base line can be verified without landing on the edge gateway.
frontend wetware_base
  bind 0.0.0.0:2223
  default_backend host_core

backend host_core
  server core 10.66.0.4:22 check inter 1s fall 3 rise 2
EOF
systemctl restart haproxy
sleep 0.5
ss -ltn | grep -q ':2222' || { echo "port 2222 not listening" >&2; exit 1; }
ss -ltn | grep -q ':2223' || { echo "port 2223 not listening" >&2; exit 1; }
echo "[entry] 2222 -> ${CONTAINER_IP}:22, 2223 -> 10.66.0.4:22 (baseline acceptance)"
