"""Wrapper around the Qloo hackathon API.

Falls back to MOCK data when QLOO_API_KEY is missing so the CLI still runs.

A few things here look odd but are deliberate, and all of them came from actually
hitting the API rather than reading the docs:

  - Cuisine tags go in filter.tags, never in signal.interests.tags. Passing a
    cuisine as a signal returns a confident-looking list of the wrong places.
    As a filter, urn:tag:cuisine:qloo:kashmiri in Delhi gives you Matamaal and
    Samavar, which is correct.
  - Don't mix tag families in filter.tags. "kashmiri + restaurant" together
    returns generic junk; kashmiri on its own is fine.
  - Place queries need a category filter (bar, cafe, restaurant). Without one a
    place query seeded on music comes back with museums, malls, and at one point
    a cake delivery website.
  - Affinity scores are not comparable between calls. One call returned 1.0 for
    all 50 results. Treat them as a within-call ordering and nothing more.
"""
from __future__ import annotations

import os
from typing import Any, Iterable

import requests

BASE_URL = os.getenv("QLOO_BASE_URL", "https://hackathon.api.qloo.com").rstrip("/")
API_KEY = os.getenv("QLOO_API_KEY") or ""
MOCK = not API_KEY
TIMEOUT = int(os.getenv("QLOO_TIMEOUT", "30"))

ARTIST = "urn:entity:artist"
PLACE = "urn:entity:place"
MOVIE = "urn:entity:movie"
BOOK = "urn:entity:book"
BRAND = "urn:entity:brand"

# Venue categories. One of these is required on any place query.
CAT_RESTAURANT = "urn:tag:genre:place:restaurant"
CAT_BAR = "urn:tag:genre:place:restaurant:bar"
CAT_CAFE = "urn:tag:genre:place:restaurant:cafe"
CAT_LIVE_MUSIC = "urn:tag:genre:place:live_music_venue"

_cache: dict[tuple, Any] = {}


class QlooError(RuntimeError):
    pass


def _headers() -> dict:
    return {"X-Api-Key": API_KEY, "Accept": "application/json"}


def _get(path: str, params: dict) -> dict:
    params = {k: v for k, v in params.items() if v not in (None, "", [])}
    key = (path, tuple(sorted(params.items())))
    if key in _cache:
        return _cache[key]

    # Qloo times out fairly often, so retry before giving up. Two attempts was
    # enough in testing; three runs hit the 60s ceiling and still failed.
    last = None
    for attempt in range(3):
        try:
            r = requests.get(BASE_URL + path, params=params, headers=_headers(), timeout=TIMEOUT)
            break
        except requests.RequestException as exc:
            last = exc
    else:
        raise QlooError(f"{path} never responded: {last}")

    if r.status_code >= 400:
        raise QlooError(f"{path} returned {r.status_code}: {r.text[:300]}")
    try:
        data = r.json()
    except ValueError as exc:
        raise QlooError(f"{path} returned something that isn't JSON") from exc

    _cache[key] = data
    return data


def _items(payload: dict) -> list[dict]:
    """Qloo has returned both {"results": [...]} and {"results": {"entities": [...]}}."""
    results = payload.get("results", payload)
    if isinstance(results, list):
        return [x for x in results if isinstance(x, dict)]
    if isinstance(results, dict):
        for field in ("entities", "tags"):
            if isinstance(results.get(field), list):
                return [x for x in results[field] if isinstance(x, dict)]
    return []


def entity_id(entity: dict) -> str | None:
    return entity.get("entity_id") or entity.get("id")


def affinity(entity: dict) -> float | None:
    q = entity.get("query")
    if isinstance(q, dict) and isinstance(q.get("affinity"), (int, float)):
        return float(q["affinity"])
    return None


def search_entity(name: str, entity_type: str | None = None, city: str | None = None) -> dict | None:
    """Look up a name and return the best match.

    `city` is worth passing for places. Searching "Kunzum Travel Cafe" without it
    matched a Travel Cafe in Moscow.
    """
    if MOCK:
        return {"entity_id": f"mock:{name.lower()}", "name": name, "subtype": entity_type}

    results = _items(_get("/search", {"query": name, "types": entity_type, "take": 5}))
    if not results:
        return None
    if city:
        for r in results:
            addr = (r.get("properties") or {}).get("address") or ""
            if city.lower() in addr.lower():
                return r
    return results[0]


def search_entities(names: Iterable[str], entity_type: str | None = None,
                    city: str | None = None) -> list[dict]:
    found = []
    for name in names:
        try:
            hit = search_entity(name, entity_type, city)
        except QlooError:
            continue
        if hit and entity_id(hit):
            found.append(hit)
    return found


def find_tag(query: str) -> dict | None:
    if MOCK:
        return {"id": f"urn:tag:cuisine:qloo:{query.lower()}", "name": query.title()}
    tags = _items(_get("/v2/tags", {"filter.query": query, "take": 5}))
    return tags[0] if tags else None


def insights(
    *,
    filter_type: str,
    entity_ids: list[str] | None = None,
    signal_tags: list[str] | None = None,
    city: str | None = None,
    filter_tag: str | None = None,
    take: int = 20,
) -> list[dict]:
    """The recommendation call.

    The filter/signal split matters and isn't obvious from the docs. Asking for
    artists with the qawwali genre tag:

        filter_tag  -> Nusrat Fateh Ali Khan, Rahat Fateh Ali Khan, Abida Parveen
                       i.e. artists who ARE qawwali singers
        signal_tags -> Junaid Jamshed, Hadiqa Kiani, Tina Sani
                       i.e. who qawwali listeners also listen to

    Both are useful, they just answer different questions. Only pass one
    `filter_tag` — stacking tags from different families returns junk.
    """
    if MOCK:
        return _MOCK.get(filter_type, [])[:take]

    params: dict[str, Any] = {"filter.type": filter_type, "take": min(take, 50)}
    if entity_ids:
        params["signal.interests.entities"] = ",".join(entity_ids)
    if signal_tags:
        params["signal.interests.tags"] = ",".join(signal_tags)
    if city:
        params["filter.location.query"] = city
    if filter_tag:
        params["filter.tags"] = filter_tag

    return _items(_get("/v2/insights", params))


def summarize(entity: dict) -> dict:
    props = entity.get("properties") or {}
    tags = entity.get("tags") or []
    return {
        "name": entity.get("name"),
        "qloo_id": entity_id(entity),
        "type": entity.get("subtype") or entity.get("type"),
        "affinity": affinity(entity),
        "popularity": entity.get("popularity"),
        "neighborhood": props.get("neighborhood"),
        "address": props.get("address"),
        "tags": [t.get("name") for t in tags if isinstance(t, dict) and t.get("name")][:6],
    }


_MOCK = {
    PLACE: [
        {"entity_id": "mock:1", "name": "Matamaal", "subtype": PLACE,
         "query": {"affinity": 0.9}, "properties": {"neighborhood": "Pandara Road"},
         "tags": [{"name": "Kashmiri"}]},
        {"entity_id": "mock:2", "name": "The Piano Man Jazz Club", "subtype": PLACE,
         "query": {"affinity": 0.88}, "properties": {"neighborhood": "Safdarjung Enclave"},
         "tags": [{"name": "Live music"}]},
    ],
    ARTIST: [
        {"entity_id": "mock:3", "name": "Nusrat Fateh Ali Khan", "subtype": ARTIST,
         "query": {"affinity": 0.95}},
    ],
    MOVIE: [
        {"entity_id": "mock:4", "name": "Andhadhun", "subtype": MOVIE, "query": {"affinity": 0.9}},
    ],
}
