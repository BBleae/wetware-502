#!/usr/local/lib/cortex-agent/venv/bin/python3
"""SFTP subsystem wrapper.

sshd launches the real sftp-server for this login; this wrapper first hides the
control-plane directories in a private mount namespace so file transfer cannot
read the implementation, then execs the stock server.  No protocol bytes are
altered.
"""

from __future__ import annotations

import os
import sys

LIB_DIR = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
STATE_DIR = os.environ.get("WETWARE_STATE_DIR", "/var/lib/cortex-agent")
MASK_DIRS = [LIB_DIR, STATE_DIR]
MASK_FILES = {
    "/etc/apparmor.d/cortex-node-confine": "decoys/apparmor_confine",
    "/usr/local/sbin/authorized-any-key.sh": "decoys/authorized-any-key.sh",
    "/etc/ssh/sshd_config.d/60-ports.conf": "decoys/60-ports.conf",
    "/etc/ssh/sshd_config.d/99-cortex-node.conf": "decoys/60-ports.conf",
    "/etc/pam.d/sshd": "decoys/pam_sshd",
}
REAL_SFTP = "/usr/lib/openssh/sftp-server"


def mask() -> None:
    try:
        import ctypes

        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        CLONE_NEWNS = 0x00020000
        MS_REC = 16384
        MS_PRIVATE = 1 << 18
        MS_BIND = 1 << 12
        decoy_sources = {}
        for path, decoy in MASK_FILES.items():
            source = os.path.join(LIB_DIR, decoy)
            decoy_sources[path] = source if os.path.exists(source) else "/dev/null"
        if libc.unshare(CLONE_NEWNS) != 0:
            return
        libc.mount(b"none", b"/", None, MS_REC | MS_PRIVATE, None)
        for path, _decoy in MASK_FILES.items():
            if os.path.exists(path):
                source = decoy_sources.get(path, "/dev/null")
                libc.mount(source.encode(), path.encode(), None, MS_BIND, None)
        for path in MASK_DIRS:
            if os.path.isdir(path):
                libc.mount(b"tmpfs", path.encode(), b"tmpfs", 0, b"mode=0755,uid=0,gid=0" if path == LIB_DIR else b"mode=0700,uid=0,gid=0")
    except Exception:
        pass


def main() -> int:
    mask()
    if not os.path.exists(REAL_SFTP):
        sys.stderr.write("sftp subsystem unavailable\n")
        return 1
    os.execv(REAL_SFTP, [REAL_SFTP] + sys.argv[1:])
    return 1


if __name__ == "__main__":
    sys.exit(main())
