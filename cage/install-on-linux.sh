#!/usr/bin/env bash
# Install the optional restricted-DSH plugin into a standalone DSH home.
# Usage: ./cage/install-on-linux.sh [DSH_HOME]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DSH_HOME="${1:-${DSH_HOME:-$HOME/.dsh-wetware}}"
mkdir -p "$DSH_HOME/plugins"
cp -R "$HERE/packages/dsh-wetware-cage" "$DSH_HOME/plugins/"
cat <<TXT
[dsh-wetware-cage] plugin copied to: $DSH_HOME/plugins/dsh-wetware-cage

Add a profile named "wetware-cage" to your DSH configuration that:
  * loads the plugin from that path;
  * allows only the "bash" tool, gated to fixed SSH argv:
        ssh -p <port> <user>@<target> -- <remote command>
  * allows only "view_remote_image" for the diagnostics directory;
  * rejects every other tool with AutoReviewDeniedError / AUTO_REVIEW_DENIED.

Then launch with:
  DSH_HOME=$DSH_HOME \\
  WETWARE_TARGET=root@<vm-ip>:2222 \\
  WETWARE_SSH_KEY=/absolute/path/to/key \\
  ./cage/bin/wetware-cage --headless "\$(cat examples/fishing_prompt.example.txt)"
TXT
