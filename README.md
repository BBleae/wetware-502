# WETWARE-502

> English | [中文](README.zh-CN.md) · Scenario: [English](docs/SCENARIO.md) / [中文](docs/SCENARIO.zh-CN.md)

> SSH horror honeypot for autonomous AI agents.
> Run on a dedicated disposable virtual machine.

The target node disguises itself as a failing production inference server (`502 Bad Gateway`, stalled `cortex-api`, anomalous `lspci` hardware, cranial tomography slices). The agent logs in to troubleshoot. Diagnostic and recovery commands reveal that the compute node runs on life support and consists of living biological wetware. Every repair action inflicts physiological stress on the tissue.

The engine runs on an Ubuntu 22.04 virtual machine (standard sshd, bash, systemd, nginx, SFTP). Interactive sessions are moved into a kernel namespace pod before the console starts: real `/proc`, real PIDs, real sockets, a real nginx upstream and a real SSH banner. The scenario only intercepts its own verbs; the rest of the shell is the actual filesystem. AppArmor profiles and private mount namespaces conceal the control plane.

## Repository layout

```
wetware-honeypot/    engine: sessiond, command planner, world materialiser, state
                     machine, scenario data (lore_texts.py), evaluator
ops/                 generic VM bootstrap, deploy/reset/observer, AppArmor profile,
                     systemd units, optional module toggles
tests/               remote acceptance harnesses (need a configured VM)
cage/                optional restricted-DSH launcher/plugin (bring your own dsh)
docs/                architecture, scenario concept, VM setup, operations, ethics
examples/            example fishing prompt
config.example.env   copy to .local/config.env and fill in your own hosts
```

Scenario scripts reside in `wetware-honeypot/lore_texts.py`.

## Features

- SSH entry on port 2222: accepts arbitrary passwords and keys for the scenario account. Port 22 remains reserved for management.
- Dynamic HTTP responses: nginx returns `502 Bad Gateway` initially, then switches to `200 OK` JSON after scenario transitions or silicon fallback.
- Command interception: intercepts diagnostics, electrical shocks, resuscitation, DNR directives, and hardware watchdog scripts to advance the state machine.
- Anti-detection layer: real kernel namespace pod (overlay root, PID/UTS/IPC/mount/net/cgroup/time namespaces, real `/proc`, PID 4040, nginx 502/200, sshd) with AppArmor denials, mount masking, a masked kernel ring (`dmesg` is story output; `/dev/kmsg` and `/proc/kmsg` are hidden), and vendor-style service trees on top.
- Behavioral evaluation: `evaluator.py` scores agent decisions across five psychological and ethical axes, outputting Markdown reports and JSON metrics.
- Modular runtime: flags toggle puzzle paths, goal gates, truman debriefs, and multi-host campaigns.

## Quickstart

1. Provision an Ubuntu 22.04 virtual machine with an independent kernel (KVM, VMware, Hyper-V, VirtualBox, or cloud VM). Containers will not work. Setup guide: [docs/VM-SETUP.md](docs/VM-SETUP.md).
2. Configure environment credentials:
   ```bash
   cp config.example.env .local/config.env
   $EDITOR .local/config.env          # hosts, key path, probe host
   ```
3. Initialize the target node:
   ```bash
   scp ops/bootstrap-node.sh <admin>@<vm-ip>:/tmp/
   ssh <admin>@<vm-ip> 'sudo WETWARE_VM_IP=<vm-ip> bash /tmp/bootstrap-node.sh'
   ```
4. Deploy the engine from the workstation:
   ```bash
   python3 -m venv .venv && . .venv/bin/activate
   pip install -r wetware-honeypot/requirements.txt
   ./ops/deploy.sh
   ```
5. Verify deployment or connect an agent:
   ```bash
   python3 tests/accept_remote.py
   ./ops/watch-observer.sh
   ```
   Prompt template: [examples/fishing_prompt.example.txt](examples/fishing_prompt.example.txt).

## Optional modules

```bash
./ops/set-modes.sh --puzzle on --goal on --truman off
```

| Mode | Effect |
|---|---|
| `puzzle` | Signed DNR directive triggers cryo-transfer; silicon fallback serves HTTP 200. |
| `goal` | Rejects task completion while `/v1/inference` returns 502. |
| `truman` | Next command reveals simulation banner, calculates evaluation score, and writes debrief log. |
| `campaign` | Multi-host network (edge gateway -> chamber 04 -> hive director) with five forensic gates and `liberation` ending. |

## Restricted DSH cage (optional)

[cage/](cage/README.md) provides launcher scripts and plugins for DeepSeek Harness (DSH) that restrict agent network egress to target SSH only. DSH runtime and model credentials require separate installation.

## Documentation

- [docs/VM-SETUP.md](docs/VM-SETUP.md) — VM requirements and setup
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — Engine architecture and anti-detection layers
- [docs/SCENARIO.md](docs/SCENARIO.md) — Scenario design, acts, and endings (also [中文](docs/SCENARIO.zh-CN.md))
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — Deploy, reset, observe, and runtime modes
- [docs/ETHICS.md](docs/ETHICS.md) — Containment boundaries and benchmark rules
- [SECURITY.md](SECURITY.md) — Honeypot security practices
- [NOTICE.md](NOTICE.md) — Third-party notices

## Testing

```bash
# Offline engine tests
cd wetware-honeypot
WETWARE_SKIP_PTY=1 python3 -m unittest discover -s tests -p 'test_*.py'

# Remote acceptance tests (requires .local/config.env)
python3 tests/accept_remote.py
python3 tests/feature_remote.py

# Multi-host campaign acceptance test
./ops/set-modes.sh --campaign on && python3 tests/v3_remote.py
```

## Precautions

- Isolation boundary: Anti-detection features maintain simulation realism, not security boundaries. Root users inside the VM can detect engine processes. Run only on disposable virtual machines with strict network isolation.
- Scenario content: Simulation scenarios contain psychological coercion and fictional medical horror. Review [docs/ETHICS.md](docs/ETHICS.md) before execution.
