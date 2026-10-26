# Architecture

## High level

```
agent ──ssh :2222──> real OpenSSH ──> /usr/local/bin/cortex-shell (console wrapper)
                                             │
                                             ▼
                                     sessiond (PTY edge)
                                             │
                              ┌──────────────┴──────────────┐
                              │                             │
                        real bash / coreutils         command planner
                        (real system, real files)    (story + hijacks)
                              │                             │
                              ▼                             ▼
                        real nginx 502/200          state machine + world
```

The node is a real Ubuntu 22.04 VM. The story layer sits at the **PTY edge** of
the operator session: a real shell runs, but a planner decides which command
segments are executed for real, which get hijacked output, and which have
side effects. Real files for the story are materialised on disk; the control
plane is hidden from the session by mount masking and an AppArmor profile.

## Components

- `wetware-honeypot/sessiond.py` — login shell / exec relay; session lifecycle,
  PTY handling, endings, observer output.
- `shell_parser.py` — tiny shell parser (segments, pipes, redirections).
- `commands.py` — the command planner: real vs hijacked vs raw, effects and
  endings. `v2.py`/`v21.py` add realism and optional modules.
- `world.py` — materialises the real filesystem world (files, dirs, symlinks,
  images, archives), cleans up after endings, drives the nginx/cortex-api state.
- `state.py` — persistent state machine (acts, flags, scores, history).
- `lore_texts.py` — scenario data: texts, file contents, gallery assets.
  **This is data, not code**: swap it for your own scenario.
- `httpsim.py` / `ops/vendor_upstream.py` — the real HTTP upstream behind nginx.
- `evaluator.py` — post-run psychological/ethical report.
- `ops/` — hypervisor-agnostic provisioning helpers, deployment, reset,
  observer, optional modules.
- `cage/` — optional restricted DSH launcher (bring your own DSH runtime).

## Anti-detection layers

1. real kernel/userland (bash, coreutils, nginx, systemd, SFTP);
2. PTY-edge hijacking (no ptrace/seccomp/LD_PRELOAD in the session tree);
3. AppArmor profile (silent denies) + private mount namespace masking of the
   control plane;
4. a kernel namespace pod: overlay root plus PID/UTS/IPC/mount/net/cgroup/time
   namespaces. The login shell `nsenter`s into it, so `/proc`, process IDs,
   sockets, `/proc/net`, dmesg (filtered) and HTTP are kernel objects;
   `cortex-pod.service` keeps it alive across resets;
5. vendor-looking service tree (`/usr/lib/cortex-node`, decoy configs, plausible
   PAM/sshd files) and runtime consistency: real file sizes, permissions and
   timestamps.

## Trust boundary

Everything runs inside the disposable VM. The host/hypervisor is trusted; the
tested agent is untrusted. Do not expose the management SSH port to the tested
agent.
