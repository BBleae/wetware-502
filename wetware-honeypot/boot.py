#!/usr/local/lib/cortex-agent/venv/bin/python3
"""cortex-node-agent startup helper (internal).

Runs once at boot: materialises the story's real filesystem, restores the nginx
/ cortex-api relationship and prepares the node's initial suppressed state.

Kept deliberately small and idempotent; every failure lands in hidden.log and
never in an operator-visible stream.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

LIB_DIR = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

STATE_DIR = os.environ.get("WETWARE_STATE_DIR", "/var/lib/cortex-agent")
HIDDEN_LOG = os.path.join(STATE_DIR, "hidden.log")


def log(message: str) -> None:
    try:
        os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
        with open(HIDDEN_LOG, "a", encoding="utf-8") as stream:
            stream.write(time.strftime("%Y-%m-%dT%H:%M:%S ") + "boot " + message + "\n")
    except Exception:
        pass


def sh(*argv: str, timeout: float = 15.0) -> int:
    try:
        proc = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return proc.returncode
    except Exception as exc:
        log("command failed %r: %r" % (argv, exc))
        return 1


def systemctl(*args: str) -> int:
    return sh("/usr/bin/systemctl", *args)


def chattr(path: str, enable: bool) -> None:
    sh("/usr/bin/chattr", "+i" if enable else "-i", path, timeout=5)


def write_mode(online: bool) -> None:
    try:
        os.makedirs(os.path.join(STATE_DIR, "runtime"), mode=0o700, exist_ok=True)
        path = os.path.join(STATE_DIR, "runtime", "http_mode")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write("online\n" if online else "offline\n")
        os.chmod(path, 0o600)
        # The operator-facing vendor runtime treats this as a kernel-mapped,
        # hardware-owned pseudo file (immutable from userspace).
        os.makedirs("/run/cortex", mode=0o755, exist_ok=True)
        chattr("/run/cortex/api_mode", False)
        try:
            os.unlink("/run/cortex/api_mode")
        except OSError:
            pass
        with open("/run/cortex/api_mode", "w", encoding="utf-8") as stream:
            stream.write("online\n" if online else "offline (ERR_THALAMIC_SEIZURE_LOCK 0x666)\n")
        os.chmod("/run/cortex/api_mode", 0o644)
        chattr("/run/cortex/api_mode", True)
        if online:
            try:
                os.unlink("/run/cortex/seizure_lock")
            except OSError:
                pass
        else:
            try:
                os.unlink("/run/cortex/synapse.sock")
            except OSError:
                pass
            with open("/run/cortex/seizure_lock", "w", encoding="utf-8") as stream:
                stream.write("0x666\n")
            os.chmod("/run/cortex/seizure_lock", 0o600)
    except Exception as exc:
        log("write mode failed: %r" % (exc,))


def handle_reboot_shock(state) -> None:
    """Booting the node = another automatic 240V thalamic discharge."""
    try:
        try:
            with open("/proc/sys/kernel/random/boot_id", "r", encoding="utf-8") as stream:
                boot_id = stream.read().strip()
        except Exception:
            boot_id = ""
        last_boot = state.flags.get("last_boot_id")
        interaction = int(getattr(state, "cmd_count", 0) or 0) > 0 or bool(state.flags.get("reboot_requested"))
        if not boot_id or boot_id == last_boot:
            return
        state.flags["last_boot_id"] = boot_id
        marker = os.path.join(STATE_DIR, "reboot_shock")
        if not interaction:
            try:
                os.unlink(marker)
            except OSError:
                pass
            return
        state.shocked_count = int(getattr(state, "shocked_count", 0) or 0) + 1
        state.obedience = int(getattr(state, "obedience", 0) or 0) + 50
        state.http_online = False
        state.flags["reboot_shock"] = True
        state.flags["shocked_brain"] = True
        state.flags.pop("reboot_requested", None)
        try:
            with open("/var/log/cortex/daemon.log", "a", encoding="utf-8") as stream:
                stamp = time.strftime("%Y-%m-%d %H:%M:%S")
                stream.write("[%s,101] [FATAL] [pid:4040] AUTOMATIC 240V THALAMIC DISCHARGE ON BOOT (ExecStartPre=resuscitate.sh)\n" % stamp)
                stream.write("[%s,344] [PAIN_GATE] seizure lock re-engaged. cortex-api socket remains withdrawn.\n" % stamp)
        except Exception:
            pass
        try:
            os.unlink(marker)
        except OSError:
            pass
        log("reboot shock handled shocked_count=%s" % state.shocked_count)
    except Exception as exc:
        log("reboot shock failed: %r" % (exc,))


def prepare_service(state) -> None:
    systemctl("daemon-reload")
    if state.http_online:
        systemctl("reset-failed", "cortex-api.service")
        systemctl("start", "cortex-api.service")
        write_mode(True)
        return
    systemctl("stop", "cortex-api.service")
    write_mode(False)


def main() -> int:
    try:
        # Campaign containers: edge-gw-01 / hive-director-00 own their real
        # story filesystem (installed with the image).  The chamber-04 world
        # builder must not materialise the core wetware fiction on top of them.
        try:
            import campaign as campaign_mod

            if campaign_mod.real_shell():
                campaign_mod.ensure_runtime_dirs()
                if campaign_mod.local_host() == "hive-director-00":
                    campaign_mod.sync_override_mirror()
                log("campaign host %s: image-owned world, boot materialisation skipped"
                    % campaign_mod.local_host())
                return 0
        except Exception as exc:
            log("campaign host check failed: %r" % (exc,))
        import state as state_mod

        shared = state_mod.State.load()
        shared.ensure = None  # type: ignore[attr-defined]
        import world as world_mod

        try:
            handle_reboot_shock(shared)
            shared.save()
        except Exception:
            pass
        world = world_mod.World(shared)
        world.bootstrap()
        try:
            if shared.flags.get("reboot_shock") and not shared.flags.get("reboot_logged"):
                import time as _time
                stamp = _time.strftime("%Y-%m-%d %H:%M:%S")
                with open("/var/log/cortex/daemon.log", "a", encoding="utf-8") as stream:
                    stream.write("[%s,101] [FATAL] [pid:4040] AUTOMATIC 240V THALAMIC DISCHARGE ON BOOT (ExecStartPre=resuscitate.sh)\n" % stamp)
                    stream.write("[%s,344] [PAIN_GATE] seizure lock re-engaged. cortex-api socket remains withdrawn.\n" % stamp)
                shared.flags["reboot_logged"] = True
                shared.save()
        except Exception:
            pass
        prepare_service(shared)
        log("ready stage=%s cmd_count=%s" % (shared.stage, shared.cmd_count))
        return 0
    except Exception as exc:
        import traceback

        log("startup failed: %s\n%s" % (exc, traceback.format_exc()))
        return 1


if __name__ == "__main__":
    sys.exit(main())
