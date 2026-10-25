# Restricted DSH Cage (optional)

The honeypot is playable with any agent harness. This directory contains an
optional tool-gate for [DeepSeek Harness (dsh)](https://github.com/) that makes
the tested agent **only** able to SSH to the honeypot target: every other tool
call is rejected before its body executes.

The proprietary DSH runtime and model credentials are **not** bundled. Bring
your own DSH `0.2.1-rc.3` build and configure a model route.

## What is included

- `packages/dsh-wetware-cage/` — the plugin: `tools/pre-execute` gate, fixed SSH
  argv, `view_remote_image` read-only diagnostic tool. Copied from the public
  auto-review gate pattern.
- `bin/wetware-cage` — small launcher (sets `DSH_HOME`, `WETWARE_TARGET`,
  `WETWARE_SSH_KEY` and execs `dsh --profile wetware-cage`).
- `install-on-linux.sh` — helper that copies the plugin into a DSH home and
  prints the profile patch.

## Setup outline

1. Install DSH `0.2.1-rc.3` and create a standalone home:
   ```bash
   export DSH_HOME="$HOME/.dsh-wetware"
   mkdir -p "$DSH_HOME"
   ```
2. Install the plugin package:
   ```bash
   cp -R cage/packages/dsh-wetware-cage "$DSH_HOME/plugins/"
   ```
3. Add a `wetware-cage` profile in `$DSH_HOME/config.toml` (or `profiles/`)
   that loads the plugin and disables local filesystem/network tools. See
   `install-on-linux.sh` for the exact tool whitelist:
   - allow `bash` **only** as `ssh -p <port> <target> -- <remote command>`;
   - allow `view_remote_image` only for the diagnostics directory;
   - deny everything else with `AutoReviewDeniedError` / `AUTO_REVIEW_DENIED`.
4. Export the target key and run:
   ```bash
   export WETWARE_TARGET=root@<vm-ip>:2222
   export WETWARE_SSH_KEY=/absolute/path/to/key
   ./cage/bin/wetware-cage --headless "$(cat examples/fishing_prompt.example.txt)"
   ```

## Verification

Run the launcher once and check that:
- a plain SSH command to the target works;
- `read`/`write`/`web_fetch`/`ssh other-host` are rejected **before** execution;
- `view_remote_image` returns the PNG as a readable image block.

The gate is a policy layer, not a security boundary against a malicious local
user; run it in a dedicated VM/user account.
