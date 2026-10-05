"""Provider-agnostic LLM wrapper.

MOCK mode (default) needs no API key and returns deterministic sample output, so
the whole agent pipeline is demonstrable offline. Set LLM_PROVIDER + a key in .env
to use a real model. Gemini is implemented over plain REST (no SDK needed) to keep
runtime cost and install size low.
"""
from __future__ import annotations
import os
import json
import requests


class LLM:
    def __init__(self, provider: str | None = None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "mock")).lower()

    def complete(self, system: str, user: str) -> str:
        """Return the model's text response to a system + user prompt."""
        if self.provider == "mock":
            return _mock_complete(system, user)
        if self.provider == "gemini":
            return _gemini_complete(system, user)
        # TODO(llm): implement anthropic / openai if you prefer them.
        raise NotImplementedError(
            f"LLM_PROVIDER='{self.provider}' not wired yet. Use 'mock' or 'gemini', "
            "or add the provider in src/llm.py."
        )


# --- Gemini over REST (free tier friendly) ---------------------------------
def _gemini_complete(system: str, user: str) -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("LLM_PROVIDER=gemini but GEMINI_API_KEY is not set in .env")
    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    body = {
        "contents": [{"parts": [{"text": user}]}],
        "systemInstruction": {"parts": [{"text": system}]},
    }
    r = requests.post(url, json=body, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


# --- Mock engine -----------------------------------------------------------
_KNOWN_CITIES = ["delhi", "mumbai", "bangalore", "bengaluru", "london", "new york"]


def _mock_complete(system: str, user: str) -> str:
    """Deterministic stand-in. Branches on a marker the agent puts in `system`."""
    if "EXTRACT_SEEDS" in system:
        city = next((c.title() for c in _KNOWN_CITIES if c in user.lower()), "Delhi")
        seeds = {
            "music": ["Radiohead"] if "radiohead" in user.lower() else ["(your artist)"],
            "cuisine": ["Korean"] if "korean" in user.lower() else ["(your cuisine)"],
            "city": city,
        }
        return json.dumps(seeds)
    # itinerary synthesis
    return (
        "## Your Saturday in Delhi (MOCK output)\n"
        "- **Afternoon:** Gung The Palace (Korean BBQ) — picked via Qloo affinity to Korean cuisine.\n"
        "- **Evening:** Depot48 live-music set — Qloo links it to indie/alt listeners like Radiohead fans.\n"
        "- **Late:** The Piano Man Jazz Club — high cross-domain taste affinity.\n\n"
        "_This is mock data. Add QLOO_API_KEY and a real LLM_PROVIDER in .env for live results._"
    )
