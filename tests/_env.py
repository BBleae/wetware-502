"""Environment/config helper for the remote acceptance scripts.

Real hosts/keys live in .local/config.env (gitignored). The public default is a
placeholder from config.example.env so nothing private is committed.
"""
from __future__ import annotations

import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load() -> dict:
    data = {}
    for candidate in (ROOT / "config.example.env", ROOT / ".local" / "config.env"):
        try:
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                data[key.strip()] = value.strip().strip('"').strip("'")
        except FileNotFoundError:
            continue
    return data


_DATA = _load()


def get(key: str, default: str = "") -> str:
    return os.environ.get(key) or _DATA.get(key) or default


def split_target(value: str, user: str = "root", port: int = 2222) -> tuple:
    """Parse 'user@host:port' (password ignored)."""
    user_part, _, host_part = value.rpartition("@") if "@" in value else ("", "", value)
    user = user_part or user
    host, _, port_part = host_part.partition(":")
    return user, host, int(port_part) if port_part.isdigit() else port
