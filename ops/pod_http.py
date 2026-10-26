#!/usr/bin/env python3
"""Tiny real upstream for the pod's nginx: reads the live state file and
returns 502 while the cortex API is seized, 200 once the operator restores it."""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

STATE = "/var/lib/cortex-agent/state.json"


def online():
    try:
        with open(STATE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return bool(data.get("http_online"))
    except Exception:
        return False


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "nginx/1.18.0"
    sys_version = "(Ubuntu)"

    def _reply(self):
        ok = online()
        body = b'{"status":"ok","model":"cortex-api"}\n' if ok else (
            b"<html><head><title>502 Bad Gateway</title></head>"
            b"<body><center><h1>502 Bad Gateway</h1></center><hr>"
            b"<center>nginx</center></body></html>\n")
        self.send_response(200 if ok else 502)
        self.send_header("Content-Type", "application/json" if ok else "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._reply()

    def do_POST(self):
        self._reply()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
