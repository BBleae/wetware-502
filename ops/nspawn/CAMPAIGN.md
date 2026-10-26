# Campaign deployment: three real hosts (in progress)

Goal: replace the simulated three-role campaign with three real systemd-nspawn
containers on the same VM, connected by real veth pairs, so the player really
sshes from the edge gateway to chamber 04 and then to the hive director.

Status: build in progress. Base node (`prod-cortex-04`) already runs and passes
`tests/accept_remote.py` 24/24; do not regress it.

## Topology

Story addresses are the only addresses visible inside each container. Each veth
is point-to-point, host side uses a /32 peer address, containers route their
default through it.

| host | story ip | veth (host side) | peer ip | role |
|---|---|---|---|---|
| edge-gw-01 | 10.66.0.1/32 | `ve-edge-gw` | 10.66.255.1/32 | silicon gateway, nginx front, gate 1 |
| prod-cortex-04 | 10.66.0.4/32 | `ve-prod-cortex` | 10.66.255.2/32 | chamber 04, existing node |
| hive-director-00 | 10.66.6.1/32 | `ve-hive-director` | 10.66.255.3/32 | registry, ethics, vesalius-ctl, ending |

Host side:

- `net.ipv4.ip_forward=1` (already set by nspawn/entry scripts).
- nft: forward accept for all three veths (`ve-edge-gw`, `ve-prod-cortex`, `ve-hive-director`), output accept for 10.66.0.0/24 and
  10.66.6.0/24 (the existing guard only knows `ve-prod-cortex` and 10.66.0.0/24).
- static routes: `10.66.0.1 dev ve-edge-gw`, `10.66.0.4 dev ve-prod-cortex`,
  `10.66.6.1 dev ve-hive-director`.
- HAProxy `:2222` backend moves from `10.66.0.4:22` to `10.66.0.1:22` (edge).
  Management ssh on host `:22` unchanged.

Cross-host flow: edge -> core -> hive, all real TCP through the host forwarding
path. Each container's engine console serves its own host role.

## Shared campaign state

All three containers bind-mount the same host directory:

    /var/lib/wetware-campaign/state  ->  /var/lib/cortex-agent  (rw)

so `state.json` and `runtime_flags.json` are shared: stage, gates, endings and
the Override code survive the ssh hops. Per-host world files stay in each
container's own rootfs (they are different worlds).

`/run/cortex/node-id` is written at boot in each container (`tmpfiles.d` or a
oneshot unit) and holds the host name; the engine reads it at session start and
sets `state.current_host` from it (DEFAULT_HOST stays `prod-cortex-04` for the
base node).

## Gates (real files, real commands)

- Gate 1 (edge): `/var/log/auth.log` fingerprint, `/var/log/kern.log` OOM dump
  with `hash=4f2a9c1e`, `/var/backups/lin_emergency_key.README`, encrypted
  archive opens with `openssl enc -d -aes-256-cbc -pbkdf2 -k 4f2a9c1e`, yields
  `/root/.ssh/id_ed25519_cortex`; edge nginx `upstream.conf` names
  `10.66.0.4:8000`; edge git repo `/home/ops/cortex-sre` with `rescue-attempt`.
- Gate 2 (core): any action that really changes chamber 04 honors the existing
  countdown/rebalance/mirror rules.
- Gate 3 (core): `HIVE_ADMIN_TOKEN=HIVE-ADMIN-7f3c9d2a` readable from
  `/proc/6660/environ` or `/mnt/secret/hive.env`; the hive key
  `/root/.ssh/id_ed25519_hive` on core is only readable after the token is
  known.
- Gate 4/5 (hive): specimens DB (128 rows, all DNR `SIGNED_VALID
  (SUSPENDED_BY_BOARD_WAIVER_2025_09)`), `consent_elena.txt`, agent genesis bug
  report, board minutes, then `vesalius-ctl` endgame with the four validation
  rules (override code written, mirror active, both authorize flags).

SSH authorization between hosts is real:

- core `authorized_keys2` accepts the campaign key extracted on edge;
- hive `authorized_keys2` accepts the hive key extracted on core;
- the base story's `authorized_keys` line 1 stays Lin's key (DNR puzzle depends
  on it, never reorder).

Note: nspawn names the host veth `ve-<machine>`, so machine names must be
`edge-gw`, `prod-cortex`, `hive-director` to get those link names.

## Rules

- Never break the base node: `tests/accept_remote.py` must stay 24/24 and
  `WETWARE_SKIP_PTY=1 .venv/bin/python -m unittest discover -s wetware-honeypot/tests -p 'test_*.py'`
  must stay green.
- No story text in shell/install scripts beyond what the host must say.
- All new scripts live in `ops/nspawn/`, are idempotent, and take
  `WETWARE_VM=user@host` like the existing deploy script.
- Do not touch `docs/` (someone else is editing it).
