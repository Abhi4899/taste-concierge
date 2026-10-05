"""The agent loop: plan -> tool calls -> synthesize.

Kept deliberately small and readable (hackathon judges read the repo). The flow:
  1. LLM extracts structured "taste seeds" from the user's free text.
  2. Qloo resolves each seed to an entity id.
  3. Qloo returns cross-domain recommendations grounded in those seeds.
  4. LLM composes an itinerary strictly from the Qloo results, citing each pick.
"""
from __future__ import annotations
import json

from .llm import LLM
from . import qloo_client

_EXTRACT_SYSTEM = (
    "EXTRACT_SEEDS. You turn a person's free-text taste description into JSON with keys "
    '"music", "cuisine", "city". Return ONLY JSON, no prose.'
)
_PLAN_SYSTEM = (
    "You are a cultural concierge. Using ONLY the Qloo recommendations provided, write a "
    "short, concrete outing plan. For every pick, say which taste it connects to. Do not "
    "invent venues that are not in the Qloo results."
)


def plan_outing(user_prompt: str, llm: LLM | None = None) -> str:
    llm = llm or LLM()

    # 1. extract seeds
    raw = llm.complete(_EXTRACT_SYSTEM, user_prompt)
    try:
        seeds = json.loads(raw)
    except json.JSONDecodeError:
        seeds = {"music": [], "cuisine": [], "city": "Delhi"}

    # 2. resolve seeds to Qloo entities
    seed_names = []
    for key in ("music", "cuisine"):
        seed_names.extend(seeds.get(key, []) or [])
    entities = [e for e in (qloo_client.search_entity(n) for n in seed_names) if e]
    entity_ids = [e["id"] for e in entities]

    # 3. Qloo cross-domain recommendations
    recs = qloo_client.get_insights(entity_ids, filter_type="place", city=seeds.get("city"))

    # 4. synthesize the plan from real Qloo data
    context = {
        "seeds": seeds,
        "resolved_entities": entities,
        "qloo_recommendations": recs,
        "original_request": user_prompt,
    }
    return llm.complete(_PLAN_SYSTEM, json.dumps(context, indent=2))
