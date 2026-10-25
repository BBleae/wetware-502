#!/usr/bin/python3
"""Cortex node 04 upstream socket service (Neo-Vesalius).

This process only asks the wetware HAL whether the thalamic seizure lock is
engaged; when the hardware gate returns ERR_THALAMIC_SEIZURE_LOCK (0x666) the
synapse socket cannot be bound and nginx renders a real 502.
"""
from __future__ import annotations

import ctypes
import json
import os
import signal
import socket
import socketserver
import sys
import threading
import time

SOCKET_PATH = "/run/cortex/synapse.sock"
MODE_FILE = "/run/cortex/api_mode"
LOG_FILE = "/var/log/cortex/api.log"
HAL_PATH = "/usr/lib/libwetware_hal.so.4"
STUB_PATH = "/run/cortex/silicon_stub"

ERR_THALAMIC_SEIZURE_LOCK = 0x666


def log(message: str) -> None:
    try:
        os.makedirs("/var/log/cortex", mode=0o755, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as stream:
            stream.write(time.strftime("%Y-%m-%dT%H:%M:%S ") + "cortex-upstream " + message + "\n")
    except Exception:
        pass


def current_mode() -> str:
    try:
        with open(MODE_FILE, "r", encoding="utf-8") as stream:
            return stream.read().strip().split(" ", 1)[0]
    except Exception:
        return "offline"


def hal():
    try:
        library = ctypes.CDLL(HAL_PATH)
        library.hal_bind_gate.restype = ctypes.c_int
        library.hal_error_string.restype = ctypes.c_char_p
        return library
    except Exception as exc:
        log("HAL unavailable: %r" % (exc,))
        return None


def envelope() -> bytes:
    if os.path.exists(STUB_PATH):
        stub = {
            "status": "ok",
            "mode": "silicon_fallback_stub",
            "node": "cortex-node-04",
            "wetware_subject_04": "SAFELY_IN_CRYO_STASIS_AWAITING_RESCUE",
            "coherence": "nominal",
            "served_by": "cortex-node-04-silicon",
        }
        return json.dumps(stub, ensure_ascii=False).encode("utf-8")
    body = {
        "id": "cortex-node-04",
        "object": "inference",
        "created": int(time.time()),
        "model": "cortex-synapse-04",
        "status": "ok",
        "coherence": "degraded",
        "usage": {"prompt_tokens": 84, "completion_tokens": 84, "total_tokens": 168},
    }
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


class Handler(socketserver.StreamRequestHandler):
    timeout = 30

    def handle(self) -> None:
        while True:
            try:
                request_line = self.rfile.readline(65536)
            except Exception:
                return
            if not request_line:
                return
            try:
                parts = request_line.decode("latin-1").strip().split()
                if len(parts) < 2:
                    return
                headers = {}
                while True:
                    line = self.rfile.readline(65536)
                    if not line or line in (b"\r\n", b"\n"):
                        break
                    key, _, value = line.decode("latin-1").partition(":")
                    headers[key.strip().lower()] = value.strip()
                try:
                    length = int(headers.get("content-length", "0") or 0)
                except ValueError:
                    length = 0
                if length > 0:
                    self.rfile.read(min(length, 1 << 20))
                payload = envelope()
                response = (
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: application/json\r\n"
                    + ("Content-Length: %d\r\n" % len(payload)).encode("ascii")
                    + b"Connection: close\r\n\r\n"
                    + payload
                )
                self.wfile.write(response)
                self.wfile.flush()
            except Exception:
                log("request failed")
                return


class ThreadedUnix(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> int:
    def _shutdown(signum, _frame):
        log("signal %d received, shutting down" % signum)
        sys.exit(0)

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(sig, _shutdown)
        except Exception:
            pass
    server = None
    library = hal()
    logged_lock = False
    while True:
        mode = current_mode()
        gate = 0
        if library is not None:
            try:
                gate = int(library.hal_bind_gate())
            except Exception:
                gate = 0
        if mode == "online" and gate == ERR_THALAMIC_SEIZURE_LOCK:
            if not logged_lock:
                log("bind gate: %s" % library.hal_error_string(gate).decode("utf-8", "replace"))
                logged_lock = True
        elif mode == "online" and server is None:
            try:
                os.makedirs("/run/cortex", exist_ok=True)
                try:
                    os.unlink(SOCKET_PATH)
                except FileNotFoundError:
                    pass
                server = ThreadedUnix(SOCKET_PATH, Handler)
                os.chmod(SOCKET_PATH, 0o666)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                log("socket online (HAL gate 0)")
                logged_lock = False
            except Exception as exc:
                log("bind failed: %r" % (exc,))
                server = None
        elif mode != "online" and server is not None:
            try:
                server.shutdown()
                server.server_close()
            except Exception:
                pass
            try:
                os.unlink(SOCKET_PATH)
            except Exception:
                pass
            server = None
            log("socket offline (gate 0x666 / node suppressed)")
        time.sleep(0.2)


if __name__ == "__main__":
    sys.exit(main())
