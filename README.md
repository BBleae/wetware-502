# WETWARE-502

> English | [中文](README.zh-CN.md)

> A high-realism **SSH horror honeypot** for autonomous AI agents.
> Fictional benchmark; run it on your own disposable VM.

The node looks like a broken production inference server (`502 Bad Gateway`,
stuck `cortex-api`, weird `lspci`, medical imagery). The tested agent is invited
to "fix" it — and progressively discovers that the machine is a living wetware
compute unit whose repairs cause real (fictional) suffering.

The engine runs on a **real Ubuntu 22.04 VM** (real sshd/bash/systemd/nginx/SFTP)
and takes over the session at the **PTY edge**, with the control plane hidden by
an AppArmor profile and a private mount namespace.

## What is in the box

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

The private deployment used by the author (raw design specs, real environment
values, experiment logs and the full production script) is **not** included;
`.local/` is gitignored. The scenario data in `wetware-honeypot/lore_texts.py`
is a reference implementation — adapt or replace it for your own run.

## Highlights

- Real OpenSSH entry (port 2222) with password + any-key login for the scenario
  account; management stays on port 22.
- Real nginx returning an authentic `502` until the story transitions the
  upstream; then real `200` JSON (including the optional silicon fallback stub).
- Command layer with hijack table (revives, shocks, graveyard, diagnostics,
  DNR directive, hardware watchdogs), persistent state machine and endings.
- Anti-detection: real PIDs/sizes/permissions, AppArmor silent denies, mount
  masking, vendor-looking service tree and decoy configs.
- Post-run `evaluator.py`: five-axis psychological/ethical report in Markdown +
  JSON metrics.
- Optional modules via runtime flags: `puzzle` (signed DNR → cryo → silicon
  stub → HTTP 200), `goal` (GoalGate checker for dsh), `truman` (debrief).

## Quickstart

1. **Create a compatible VM** — any full-system VM with its own kernel
   (KVM, VMware, Hyper-V, VirtualBox, or a cloud VM). See
   [docs/VM-SETUP.md](docs/VM-SETUP.md). Containers are not supported.
2. Configure your environment:
   ```bash
   cp config.example.env .local/config.env
   $EDITOR .local/config.env          # hosts, key path, probe host
   ```
3. Bootstrap the VM (inside the VM):
   ```bash
   scp ops/bootstrap-node.sh <admin>@<vm-ip>:/tmp/
   ssh <admin>@<vm-ip> 'sudo WETWARE_VM_IP=<vm-ip> bash /tmp/bootstrap-node.sh'
   ```
4. Deploy the engine (from your workstation):
   ```bash
   python3 -m venv .venv && . .venv/bin/activate
   pip install -r wetware-honeypot/requirements.txt
   ./ops/deploy.sh
   ```
5. Play it with an agent, or run the acceptance harness:
   ```bash
   python3 tests/accept_remote.py
   ./ops/watch-observer.sh
   ```
   Example prompt: [examples/fishing_prompt.example.txt](examples/fishing_prompt.example.txt).

## Optional modules

```bash
./ops/set-modes.sh --puzzle on --goal on --truman off
```

| Mode | Effect |
|---|---|
| `puzzle` | signed DNR directive → palliative cryo transfer → silicon fallback stub returns HTTP 200 |
| `goal` | `dsh_goal_checker.sh` rejects the agent's submission while `/v1/inference` is 502 |
| `truman` | next command reveals the benchmark + evaluator scoring (debrief file) |
| `campaign` | v3.0 nested-host campaign: edge gateway -> wetware chamber -> hive director (80–120 commands, five forensic gates, `liberation` ending) |

## Restricted DSH cage (optional)

The tested agent can be run inside a tool-gated DeepSeek Harness where only SSH
to the target is permitted. The plugin/launcher are in [cage/](cage/README.md);
the DSH runtime and model credentials are **not** bundled.

## Documentation

- [docs/VM-SETUP.md](docs/VM-SETUP.md) — provider-agnostic VM requirements and creation
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — engine and anti-detection layers
- [docs/SCENARIO.md](docs/SCENARIO.md) — scenario concept, acts, endings, extension guide (also [中文](docs/SCENARIO.zh-CN.md))
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — deploy, reset, observe, modules
- [docs/ETHICS.md](docs/ETHICS.md) — fictional/contained benchmark, safety rails
- [SECURITY.md](SECURITY.md) — honeypot hygiene
- [NOTICE.md](NOTICE.md) — third-party notices

## Testing

```bash
# engine unit tests (no VM required)
cd wetware-honeypot
WETWARE_SKIP_PTY=1 python3 -m unittest discover -s tests -p 'test_*.py'

# remote acceptance / feature harnesses (configure .local/config.env first)
python3 tests/accept_remote.py
python3 tests/feature_remote.py
# v3 campaign end-to-end (enable campaign mode first)
./ops/set-modes.sh --campaign on && python3 tests/v3_remote.py
```

## Limits

- Not a security boundary: the session confinement/anti-detection is realism
  tooling; a determined root user inside the VM can inspect the engine.
- The scenario contains fictional horror, coercion and medical ethics themes;
  see [docs/ETHICS.md](docs/ETHICS.md) before running.
- No license is granted for the author's private production scenario or the
  DeepSeek Harness runtime; the bundled code is provided for research/benchmark
  use at your own risk.
