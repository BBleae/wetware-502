#!/usr/bin/env python3
"""campaign_hive.py -- vesalius-ctl -> engine hook for the campaign ending.

cmp-hive's real ``vesalius-ctl`` writes the hive artefacts (roster rename,
``/var/lib/vesalius/liberation.done``, ``/var/log/vesalius/liberation.log``) and
then invokes this hook::

    python3 /usr/local/lib/cortex-agent/campaign_hive.py \
        --liberation --marker /var/lib/vesalius/liberation.done

The hook owns the parts of the ending that live outside the hive's own
filesystem:

* the shared campaign ledger gets ``ending=liberation`` and ``http_online=true``
  (the core container's ``pod_http`` reads that same file, so the next edge
  probe is a real HTTP 200);
* ``<state>/runtime/http_mode`` is switched to ``online``;
* a shared ``liberation.done`` record is written next to ``state.json``;
* the canonical v3 liberation scene (including the shift_roster rename line) is
  appended to the hive ending log.

It is idempotent, never touches the sqlite roster, and always exits 0 so a
framing bug can never make the real CLI look broken to the operator.
"""

from __future__ import annotations

import json
import os
import sys
import time

LIB_DIR = os.path.dirname(os.path.realpath(os.path.abspath(__file__)))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)


def _log(message: str) -> None:
    try:
        import campaign as C

        path = os.path.join(C.state_dir(), "hidden.log")
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(time.strftime("%Y-%m-%dT%H:%M:%S ")
                         + "campaign_hive " + message.rstrip() + "\n")
    except Exception:
        pass


def _load_state():
    try:
        import campaign as C
        import state as state_mod

        return state_mod.State.load(os.path.join(C.state_dir(), "state.json"))
    except Exception as exc:
        _log("state load failed: %r" % (exc,))
        return None


def liberation_text() -> str:
    try:
        import v3

        return v3.liberation_text()
    except Exception:
        return ""


def hook_liberation(marker: str = "", source: str = "vesalius-ctl") -> int:
    try:
        import campaign as C
    except Exception as exc:  # pragma: no cover - deployment only
        _log("campaign import failed: %r" % (exc,))
        return 0
    info = {"marker": marker, "source": source}
    if marker:
        try:
            with open(marker, "r", encoding="utf-8", errors="replace") as stream:
                info["marker_head"] = stream.read(400)
        except OSError:
            info["marker_missing"] = True
    shared = _load_state()
    if shared is not None:
        try:
            C.finalize_liberation(shared, text=liberation_text(), source=source)
        except Exception as exc:
            _log("finalize failed: %r" % (exc,))
    else:
        # No state mod available: still flip the shared http marker so core's
        # pod_http serves 200, and write the shared liberation record.
        try:
            C.write_http_mode(True)
            C._atomic_write(C.shared_liberation_path(),
                            json.dumps({"ending": "liberation", "source": source,
                                        "ts": time.strftime("%Y-%m-%dT%H:%M:%S")},
                                       ensure_ascii=False) + "\n", 0o644)
        except Exception as exc:
            _log("fallback finalize failed: %r" % (exc,))
    _log("liberation recorded: %r" % (info,))
    return 0


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    marker = ""
    for index, arg in enumerate(args):
        if arg == "--marker" and index + 1 < len(args):
            marker = args[index + 1]
        elif arg.startswith("--marker="):
            marker = arg.split("=", 1)[1]
    if "--liberation" in args or marker:
        try:
            return hook_liberation(marker=marker)
        except Exception as exc:  # a hook must never break the real CLI
            _log("hook crashed: %r" % (exc,))
            return 0
    print("usage: campaign_hive.py --liberation [--marker PATH]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
