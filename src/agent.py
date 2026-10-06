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

from . import qloo_client as qloo
from .llm import LLM

EXTRACT = """Pull the taste signals out of what the person wrote. Reply with JSON only,
no prose and no code fences:

  artists    list of musician or band names they mentioned
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


def resolve(seeds: dict) -> tuple[list[str], list[str], list[dict]]:
    """Turn the names the person used into Qloo ids, and cuisines into tag ids."""
    entity_ids: list[str] = []
    cuisine_tags: list[str] = []
    trail: list[dict] = []

    for key, entity_type in (("artists", qloo.ARTIST), ("films", qloo.MOVIE)):
        for hit in qloo.search_entities(seeds.get(key) or [], entity_type):
            entity_ids.append(qloo.entity_id(hit))
            trail.append({"from": key, **qloo.summarize(hit)})

    for cuisine in seeds.get("cuisines") or []:
        tag = qloo.find_tag(cuisine)
        tag_id = (tag or {}).get("id")
        if tag_id:
            cuisine_tags.append(tag_id)
            trail.append({"from": "cuisines", "name": tag.get("name") or cuisine, "qloo_id": tag_id})

    return entity_ids, cuisine_tags, trail


def gather(entity_ids: list[str], cuisine_tags: list[str], city: str | None) -> dict[str, list[dict]]:
    """Ask Qloo for each domain separately, all seeded from the same tastes."""
    if not entity_ids and not cuisine_tags:
        return {}

    out: dict[str, list[dict]] = {}

    def add(name: str, **kwargs):
        try:
            rows = qloo.insights(**kwargs)
        except qloo.QlooError:
            return
        if rows:
            out[name] = [qloo.summarize(r) for r in rows]

    # One pass per cuisine, because cuisine tags can't be combined with each other
    # or with a category filter.
    for tag in cuisine_tags:
        label = tag.rsplit(":", 1)[-1]
        add(f"eat_{label}", filter_type=qloo.PLACE, city=city, cuisine_tag=tag, take=8)

    if entity_ids:
        add("bars", filter_type=qloo.PLACE, entity_ids=entity_ids, city=city,
            category=qloo.CAT_BAR, take=8)
        add("live_music", filter_type=qloo.PLACE, entity_ids=entity_ids, city=city,
            category=qloo.CAT_LIVE_MUSIC, take=6)
        add("cafes", filter_type=qloo.PLACE, entity_ids=entity_ids, city=city,
            category=qloo.CAT_CAFE, take=6)
        add("artists", filter_type=qloo.ARTIST, entity_ids=entity_ids, take=6)
        add("films", filter_type=qloo.MOVIE, entity_ids=entity_ids, take=6)

    return out


def recommend(prompt: str, llm: LLM | None = None, trace: bool = False):
    llm = llm or LLM()

    seeds = _parse_json(llm.complete(EXTRACT, prompt))
    seeds.setdefault("city", "Delhi")

    entity_ids, cuisine_tags, trail = resolve(seeds)
    results = gather(entity_ids, cuisine_tags, seeds.get("city"))

    if not results:
        text = ("Nothing in that matched a Qloo entity, so there's nothing to build on. "
                "Try naming an artist, a film or a cuisine.")
    else:
        text = llm.complete(WRITE_UP, json.dumps({
            "asked_for": prompt,
            "city": seeds.get("city"),
            "occasion": seeds.get("occasion"),
            "resolved": trail,
            "qloo_results": results,
        }, indent=2, default=str))

    if trace:
        return {"text": text, "seeds": seeds, "resolved": trail, "results": results}
    return text
