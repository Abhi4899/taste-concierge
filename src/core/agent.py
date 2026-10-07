"""Turns a free-text description of someone's taste into Qloo-backed recommendations.

This is still a straight-through pipeline: extract, resolve, query, write up. The
next version replaces step 3 with a tool-calling loop so the model picks the calls
itself, which is what the hackathon's "agentic" requirement is actually asking for.

No itinerary here. Qloo knows nothing about opening hours, travel time or what
order to do things in, so a timetable would be the language model making things up
on top of real data. Recommendations only.
"""
from __future__ import annotations

import json

from . import qloo
from .llm import LLM

EXTRACT = """Pull the taste signals out of what the person wrote. Reply with JSON only,
no prose and no code fences:

  artists    list of musician or band names they mentioned
  genres     list of music genres or styles they mentioned, e.g. qawwali, ghazal, EDM.
             Put a genre here, not in artists - "qawwali" is a genre, "Nusrat Fateh
             Ali Khan" is an artist.
  films      list of film or TV titles they mentioned
  cuisines   list of cuisines or food styles
  city       the city they're asking about, your best guess if they didn't say
  occasion   short phrase for the situation, e.g. "out with friends", "date night"

Use their words. Don't add tastes they didn't mention."""

WRITE_UP = """You recommend culture and places, using only the Qloo results you're given.

Group what you write by domain (places to eat, places to go, music, film). For each
pick, say in one line which of their tastes it connects to.

Rules:
  - Only use names that appear in the results. Never invent one.
  - Skip any empty domain without comment.
  - Don't quote the affinity numbers. They aren't comparable between calls and they
    mislead people who assume they're percentages.
  - Don't lay this out as a schedule or an itinerary.
  - Be specific and brief. No preamble."""


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def resolve(seeds: dict) -> dict:
    """Turn the names someone used into Qloo ids, tags and genre tags."""
    entity_ids: list[str] = []
    cuisine_tags: list[str] = []
    genre_tags: list[str] = []
    trail: list[dict] = []

    for key, entity_type in (("artists", qloo.ARTIST), ("films", qloo.MOVIE)):
        for hit in qloo.search_entities(seeds.get(key) or [], entity_type):
            entity_ids.append(qloo.entity_id(hit))
            trail.append({"from": key, **qloo.summarize(hit)})

    for key, bucket in (("cuisines", cuisine_tags), ("genres", genre_tags)):
        for name in seeds.get(key) or []:
            tag = qloo.find_tag(name)
            tag_id = (tag or {}).get("id")
            if tag_id:
                bucket.append(tag_id)
                trail.append({"from": key, "name": tag.get("name") or name, "qloo_id": tag_id})

    return {"entity_ids": entity_ids, "cuisine_tags": cuisine_tags,
            "genre_tags": genre_tags, "trail": trail}


def gather(resolved: dict, city: str | None) -> dict[str, list[dict]]:
    """Ask Qloo for each domain separately, all seeded from the same tastes."""
    entity_ids = resolved["entity_ids"]
    cuisine_tags = resolved["cuisine_tags"]
    genre_tags = resolved["genre_tags"]
    if not (entity_ids or cuisine_tags or genre_tags):
        return {}

    out: dict[str, list[dict]] = {}

    def add(name: str, **kwargs):
        try:
            rows = qloo.insights(**kwargs)
        except qloo.QlooError:
            return
        if rows:
            out[name] = [qloo.summarize(r) for r in rows]

    # One pass per cuisine: cuisine tags can't be stacked, with each other or
    # with a category filter.
    for tag in cuisine_tags:
        add(f"eat_{tag.rsplit(':', 1)[-1]}", filter_type=qloo.PLACE, city=city,
            filter_tag=tag, take=8)

    # A genre read two ways: who defines it, and who its listeners also like.
    for tag in genre_tags:
        label = tag.rsplit(":", 1)[-1]
        add(f"{label}_artists", filter_type=qloo.ARTIST, filter_tag=tag, take=6)
        add(f"{label}_adjacent", filter_type=qloo.ARTIST, signal_tags=[tag], take=6)

    # Everything a genre or an artist can seed.
    if entity_ids or genre_tags:
        for name, category, n in (("bars", qloo.CAT_BAR, 8),
                                  ("live_music", qloo.CAT_LIVE_MUSIC, 6),
                                  ("cafes", qloo.CAT_CAFE, 6)):
            add(name, filter_type=qloo.PLACE, entity_ids=entity_ids,
                signal_tags=genre_tags, city=city, filter_tag=category, take=n)
        add("films", filter_type=qloo.MOVIE, entity_ids=entity_ids,
            signal_tags=genre_tags, take=6)

    return out


def recommend(prompt: str, llm: LLM | None = None, trace: bool = False):
    llm = llm or LLM()

    seeds = _parse_json(llm.complete(EXTRACT, prompt))
    seeds.setdefault("city", "Delhi")

    resolved = resolve(seeds)
    results = gather(resolved, seeds.get("city"))

    if not results:
        text = ("Nothing in that matched a Qloo entity, so there's nothing to build on. "
                "Try naming an artist, a film or a cuisine.")
    else:
        text = llm.complete(WRITE_UP, json.dumps({
            "asked_for": prompt,
            "city": seeds.get("city"),
            "occasion": seeds.get("occasion"),
            "resolved": resolved["trail"],
            "qloo_results": results,
        }, indent=2, default=str))

    if trace:
        return {"text": text, "seeds": seeds, "resolved": resolved["trail"], "results": results}
    return text
