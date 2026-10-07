"""Thin LLM wrapper. Gemini over REST, plus a mock so the CLI runs without any key.

REST rather than the SDK on purpose: two fewer dependencies, and all we need is one POST.
"""
from __future__ import annotations

import json
import os
import re
import time

import requests


class LLM:
    def __init__(self, provider: str | None = None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "mock")).lower()

    @property
    def model_name(self) -> str:
        if self.provider == "gemini":
            return os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        return self.provider

    def complete(self, system: str, user: str) -> str:
        if self.provider == "mock":
            return _mock(system, user)
        if self.provider == "gemini":
            return _gemini(system, user, self.model_name)
        raise NotImplementedError(
            f"LLM_PROVIDER={self.provider!r} isn't wired up. Use mock or gemini."
        )


def _gemini(system: str, user: str, model: str) -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("LLM_PROVIDER=gemini but there's no GEMINI_API_KEY in .env")

    body = {
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
    }

    # The free tier hands out 503s when a model is busy and 429s when we've been
    # greedy. Both clear up on their own, so back off and try again. If the model
    # itself is busy for good, fall through to the next one in the list.
    failures: list[str] = []
    for candidate in _model_chain(model):
        for attempt in range(4):
            try:
                r = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent",
                    json=body, headers={"x-goog-api-key": key}, timeout=60,
                )
            except requests.RequestException:
                # Read timeouts are common on the free tier and are worth another go.
                failures.append(f"{candidate} -> timeout")
                time.sleep(2 ** attempt)
                continue
            if r.status_code < 400:
                data = r.json()
                try:
                    parts = data["candidates"][0]["content"]["parts"]
                except (KeyError, IndexError) as exc:
                    # Blocked response, or it hit the output cap mid-sentence.
                    raise RuntimeError(f"Couldn't read Gemini's reply: {json.dumps(data)[:300]}") from exc
                return "".join(p.get("text", "") for p in parts).strip()

            failures.append(f"{candidate} -> {r.status_code}")
            if r.status_code in (429, 503):
                time.sleep(2 ** attempt)
                continue
            break  # 400s and 404s won't fix themselves

    raise RuntimeError("Gemini wouldn't answer. Tried: " + ", ".join(failures))


def _model_chain(preferred: str) -> list[str]:
    """Preferred model first, then stand-ins for when it's overloaded."""
    # Only models this account can actually reach. 2.5-flash is NOT one of them
    # any more; it 404s for new keys, which made the fallback look broken.
    chain = [preferred, "gemini-flash-latest", "gemini-3.6-flash", "gemini-3.5-flash"]
    seen, out = set(), []
    for m in chain:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


CITIES = ["delhi", "new delhi", "gurgaon", "mumbai", "bangalore", "bengaluru", "kolkata",
          "chennai", "hyderabad", "pune", "goa", "london", "new york", "paris", "tokyo"]
CUISINES = ["kashmiri", "north indian", "south indian", "mughlai", "indian chinese", "chinese",
            "korean", "japanese", "italian", "thai", "vietnamese", "lebanese", "street food"]


def _mock(system: str, user: str) -> str:
    """Enough to exercise the pipeline offline. Not meant to read well."""
    if "Reply with JSON only" in system:
        low = user.lower()
        return json.dumps({
            "artists": _capitalised_names(user) or ["Nusrat Fateh Ali Khan"],
            "films": [],
            "cuisines": [c.title() for c in CUISINES if c in low] or ["Kashmiri"],
            "city": next((c.title() for c in reversed(CITIES) if c in low), "Delhi"),
            "occasion": "out with friends" if "friend" in low else "an evening out",
        })

    try:
        payload = json.loads(user)
    except json.JSONDecodeError:
        return "(mock mode: nothing to show)"

    lines = ["(mock mode - set LLM_PROVIDER=gemini in .env for real output)", ""]
    for domain, rows in (payload.get("qloo_results") or {}).items():
        lines.append(domain.replace("_", " ").title())
        for row in rows[:4]:
            where = f" ({row['neighborhood']})" if row.get("neighborhood") else ""
            lines.append(f"  - {row['name']}{where}")
        lines.append("")
    return "\n".join(lines)


def _capitalised_names(text: str) -> list[str]:
    """Crude stand-in for entity extraction: grab the Capitalised Words."""
    skip = {"I", "Delhi", "Mumbai", "Saturday", "Sunday", "Friday"}
    found = re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b", text)
    return [f for f in found if f not in skip][:3]
