"""Smoke-test the live Qloo API and dump raw JSON so we can pin the exact shapes.

Run once after putting QLOO_API_KEY in .env:

    .\.venv\Scripts\python.exe scripts\probe_qloo.py

It hits each endpoint the agent uses and prints a trimmed raw response plus the
field names it found, so any mismatch in the client's parsing shows up here first
rather than halfway through a demo.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import requests

BASE = os.getenv("QLOO_BASE_URL", "https://hackathon.api.qloo.com").rstrip("/")
KEY = os.getenv("QLOO_API_KEY") or ""


def call(label: str, path: str, params: dict) -> dict | None:
    print(f"\n{'=' * 70}\n{label}\n  GET {path}\n  params: {json.dumps(params)}")
    try:
        r = requests.get(
            f"{BASE}{path}",
            params=params,
            headers={"X-Api-Key": KEY, "Accept": "application/json"},
            timeout=30,
        )
    except requests.RequestException as exc:
        print(f"  !! connection error: {exc}")
        return None

    print(f"  -> HTTP {r.status_code}")
    if r.status_code >= 400:
        print(f"  body: {r.text[:500]}")
        return None
    try:
        data = r.json()
    except ValueError:
        print(f"  !! non-JSON body: {r.text[:300]}")
        return None

    print(f"  top-level keys: {list(data.keys())}")
    results = data.get("results", data)
    if isinstance(results, dict):
        print(f"  results keys: {list(results.keys())}")
        items = next((v for v in results.values() if isinstance(v, list)), [])
    else:
        items = results if isinstance(results, list) else []
    print(f"  items: {len(items)}")
    if items:
        print(f"  first item keys: {sorted(items[0].keys())}")
        print("  first item (trimmed):")
        print(json.dumps(items[0], indent=4, default=str)[:1500])
    return data


def first_id(data: dict | None) -> str | None:
    if not data:
        return None
    results = data.get("results", data)
    items = (
        next((v for v in results.values() if isinstance(v, list)), [])
        if isinstance(results, dict)
        else results
    )
    if not items:
        return None
    item = items[0]
    return item.get("entity_id") or item.get("id") or item.get("tag_id")


def main() -> int:
    if not KEY:
        print("QLOO_API_KEY is not set in .env — nothing to probe.")
        return 1
    print(f"Base URL: {BASE}\nKey: {KEY[:6]}...{KEY[-4:]} ({len(KEY)} chars)")

    artist = call("1. Resolve an artist by name", "/search", {"query": "Radiohead", "types": "urn:entity:artist"})
    artist_id = first_id(artist)
    print(f"\n  resolved artist id: {artist_id}")

    tag = call("2. Resolve a cuisine tag", "/v2/tags", {"filter.query": "Korean", "take": 5})
    tag_id = first_id(tag)
    print(f"\n  resolved tag id: {tag_id}")

    if artist_id:
        call(
            "3. THE CORE CALL — places in Delhi from a music taste",
            "/v2/insights",
            {
                "filter.type": "urn:entity:place",
                "signal.interests.entities": artist_id,
                "filter.location.query": "Delhi",
                "take": 5,
            },
        )
        call(
            "4. Cross-domain — artists from that artist",
            "/v2/insights",
            {"filter.type": "urn:entity:artist", "signal.interests.entities": artist_id, "take": 5},
        )
        call(
            "5. Cross-domain — films from that artist",
            "/v2/insights",
            {"filter.type": "urn:entity:movie", "signal.interests.entities": artist_id, "take": 5},
        )

    if tag_id:
        call(
            "6. Food in Delhi filtered by the cuisine tag",
            "/v2/insights",
            {
                "filter.type": "urn:entity:place",
                "signal.interests.tags": tag_id,
                "filter.location.query": "Delhi",
                "take": 5,
            },
        )

    print(f"\n{'=' * 70}\nProbe done. Anything above that returned HTTP 4xx needs a param fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
