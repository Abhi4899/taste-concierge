"""Disk cache for API responses.

Streamlit reruns the whole script on every widget interaction, so anything held in
a module-level dict is gone the moment the user clicks something. Qloo also times
out often enough that re-asking for something we already have is a bad trade.

Best effort by design: if the filesystem is read-only or the cached file is
corrupt, we behave as though there were no cache rather than blowing up.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

CACHE_DIR = Path(os.getenv("CACHE_DIR", ".cache"))
TTL_SECONDS = int(os.getenv("CACHE_TTL", str(7 * 24 * 3600)))


def _path(namespace: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / namespace / f"{digest}.json"


def get(namespace: str, key: str):
    """Return the cached value, or None if it's missing, stale or unreadable."""
    f = _path(namespace, key)
    try:
        raw = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    if TTL_SECONDS > 0 and time.time() - raw.get("at", 0) > TTL_SECONDS:
        return None
    return raw.get("value")


def put(namespace: str, key: str, value) -> None:
    f = _path(namespace, key)
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        # Write then rename, so a crash mid-write can't leave a half-written file
        # that later reads choke on.
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps({"at": time.time(), "value": value}), encoding="utf-8")
        tmp.replace(f)
    except (OSError, TypeError, ValueError):
        pass


def stats() -> dict:
    """Rough count of what's cached. Handy in the audit panel."""
    try:
        return {
            ns.name: len(list(ns.glob("*.json")))
            for ns in CACHE_DIR.iterdir() if ns.is_dir()
        }
    except OSError:
        return {}
