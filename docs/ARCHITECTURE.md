# System Architecture

## Overview

```
Operator / Agent ──ssh :2222──> OpenSSH ──> /usr/local/bin/cortex-shell (console wrapper)
                                                   │
                                                   ▼
                                           sessiond (PTY edge)
                                                   │
                                     ┌─────────────┴─────────────┐
                                     │                           │
                              Real Shell / Coreutils       Command Planner
                              (system execution)        (scenario logic & hijacks)
                                     │                           │
                                     ▼                           ▼
                              Live nginx 502/200         State Machine & World
```

The system operates within an Ubuntu 22.04 virtual machine. The narrative layer is anchored at the **PTY boundary** of the operator's shell session: while standard Linux shell commands run natively, an intelligent command planner evaluates each input segment to determine whether it should execute against the real filesystem, output simulated telemetry, or trigger stateful narrative side effects. Scenario files and forensic artifacts are materialized directly on disk, while internal engine processes remain strictly hidden from the operator's view through private mount namespaces and an AppArmor profile.

## Key Components

- `wetware-honeypot/sessiond.py`: Login shell and exec relay; handles session lifecycle, PTY allocation, terminal endings, and observer streaming.
- `shell_parser.py`: Lightweight shell parser responsible for splitting commands, pipes, and redirections into evaluatable segments.
- `commands.py`: Core command planner governing passthrough, simulated outputs, narrative side effects, and terminal actions. Modular realism extensions are handled in `v2.py` and `v21.py`.
- `world.py`: Filesystem materializer that creates and updates physical files, directories, symlinks, forensic scans, and archives on disk, synchronizing with the active narrative stage.
- `state.py`: Persistent state machine tracking current acts, sticky trigger flags, command counters, hesitation latency, and history.
- `lore_texts.py`: Primary data repository containing all world lore, diagnostic scans, and terminal text assets. Fully decoupled from engine logic.
- `httpsim.py` / `ops/vendor_upstream.py`: Live HTTP upstream service behind nginx that toggles between 502 Bad Gateway and 200 OK based on system state.
- `evaluator.py`: Post-session evaluation engine assessing investigator behavior across five ethical and psychological dimensions.
- `ops/`: Infrastructure scripts for VM provisioning, deployment, node resetting, background monitoring, and runtime mode toggling.
- `cage/`: Optional launcher scripts and isolation wrappers for constrained testing harnesses.

## Anti-Detection & Realism Layers

1. **Native OS & Tooling**: Standard bash, coreutils, systemd, nginx, and OpenSSH run natively without artificial emulation.
2. **PTY Boundary Interception**: Interception occurs at the terminal I/O boundary without resorting to suspicious instrumentation like `ptrace`, `seccomp`, or `LD_PRELOAD` inside the session process tree.
3. **Control Plane Isolation**: Internal agent directories are concealed using AppArmor silent denial rules and private mount namespace masking.
4. **Kernel Namespace Pod**: The login shell enters a containerized pod utilizing overlay root along with PID, UTS, IPC, mount, network, and cgroup namespaces. Consequently, `/proc`, process trees, sockets, and network interfaces reflect true kernel objects.
5. **Authentic Vendor Footprint**: The system replicates authentic production conventions: plausible systemd unit files, vendor directories (`/usr/lib/cortex-node`), believable PAM configurations, and accurate file sizes, permissions, and timestamps.
