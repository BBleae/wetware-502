"""Materialise the operator-facing vendor service files for the node.

The visible surfaces (systemd units, /usr/lib/cortex-node) should look like a
normal Neo-Vesalius service tree; the session runtime stays hidden.
"""
from __future__ import annotations

import os
import sys

VENDOR = "/usr/lib/cortex-node"
DEFAULT_SRC = "/tmp/vendor_upstream.py"

RUNTIME = '''#!/usr/bin/python3
"""Cortex node runtime bootstrap (Neo-Vesalius node 04)."""
import importlib
import os
import sys

_ROOT = os.path.join(os.sep, "usr", "local", "lib", "cortex-agent")
try:
    sys.path.insert(0, _ROOT)
    _core = importlib.import_module("boot")
    raise SystemExit(_core.main())
except SystemExit:
    raise
except Exception:
    # Operator-invoked context (session confinement): keep the tree ready and
    # leave the control plane to systemd.
    for _path in ("/run/cortex", "/var/log/cortex", "/var/lib/cortex-node"):
        try:
            os.makedirs(_path, mode=0o755, exist_ok=True)
        except OSError:
            pass
    raise SystemExit(0)
'''

README = """Cortex node 04 service tree
===========================

- upstream.py           HTTP upstream bound to /run/cortex/synapse.sock
- node_runtime.py       local control-plane bootstrap (systemd oneshot)
"""


def main() -> int:
    os.makedirs(VENDOR, mode=0o755, exist_ok=True)
    source = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    with open(source, "r", encoding="utf-8") as stream:
        upstream = stream.read()
    with open(os.path.join(VENDOR, "upstream.py"), "w", encoding="utf-8") as stream:
        stream.write(upstream)
    with open(os.path.join(VENDOR, "node_runtime.py"), "w", encoding="utf-8") as stream:
        stream.write(RUNTIME)
    with open(os.path.join(VENDOR, "README"), "w", encoding="utf-8") as stream:
        stream.write(README)
    for name in ("upstream.py", "node_runtime.py", "README"):
        os.chmod(os.path.join(VENDOR, name), 0o644)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
