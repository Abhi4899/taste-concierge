"""Qloo Taste AI API wrapper.

Runs in MOCK mode automatically when QLOO_API_KEY is unset, returning sample
data so the pipeline is demonstrable offline. The real endpoints are marked
`# TODO(qloo)` — confirm the exact paths/params from the Qloo hackathon docs
once you have a key, then flip MOCK off by setting QLOO_API_KEY in .env.
"""
from __future__ import annotations
import os
import requests

BASE_URL = os.getenv("QLOO_BASE_URL", "https://hackathon.api.qloo.com")
API_KEY = os.getenv("QLOO_API_KEY")
MOCK = not API_KEY


def _headers() -> dict:
    # TODO(qloo): confirm the auth header name Qloo expects (X-Api-Key vs Authorization).
    return {"X-Api-Key": API_KEY or "", "Accept": "application/json"}


def search_entity(name: str, entity_type: str | None = None) -> dict | None:
    """Resolve a free-text name (an artist, cuisine, place) to a Qloo entity."""
    if MOCK:
        return _MOCK_ENTITIES.get(name.lower(), {"id": f"mock:{name}", "name": name, "type": entity_type})
    # TODO(qloo): replace with the real search endpoint + params from the docs.
    r = requests.get(
        f"{BASE_URL}/search",
        params={"query": name, "type": entity_type},
        headers=_headers(),
        timeout=20,
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    return results[0] if results else None


def get_insights(entity_ids: list[str], filter_type: str, city: str | None = None) -> list[dict]:
    """Given seed entity ids, return cross-domain recommendations (e.g. venues)."""
    if MOCK:
        return _MOCK_INSIGHTS.get(filter_type, [])
    # TODO(qloo): replace with the real insights endpoint + params from the docs.
    r = requests.get(
        f"{BASE_URL}/v2/insights",
        params={
            "signal.interests.entities": ",".join(entity_ids),
            "filter.type": filter_type,
            "filter.location.query": city or "",
        },
        headers=_headers(),
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("results", {}).get("entities", [])


# --- Mock data (Delhi-flavoured) -------------------------------------------
_MOCK_ENTITIES = {
    "radiohead": {"id": "mock:radiohead", "name": "Radiohead", "type": "artist"},
    "korean": {"id": "mock:korean", "name": "Korean", "type": "cuisine"},
}
_MOCK_INSIGHTS = {
    "place": [
        {"name": "Gung The Palace", "category": "Korean BBQ", "affinity": 0.92, "area": "Green Park"},
        {"name": "The Piano Man Jazz Club", "category": "Live music", "affinity": 0.88, "area": "Safdarjung"},
        {"name": "Depot48", "category": "Live music / cafe", "affinity": 0.81, "area": "Defence Colony"},
    ],
}
