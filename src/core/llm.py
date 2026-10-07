"""Gemini over REST, plus a mock so the CLI runs with no key at all.

REST rather than the SDK on purpose: two fewer dependencies, and all we need is a POST.

Two things here are load-bearing and worth reading before changing anything.

**We cache the model's whole `content` object, not the text.** Gemini 3 attaches a
`thoughtSignature` to function-call parts, and the API rejects the next turn without
it: "Function call is missing a thought_signature in functionCall parts." Tested, it
is a hard 400 on both Lite models. So a cache that flattened replies to a string
would quietly break every tool loop on a cache hit. Keep the parts intact and echo
them back exactly as they arrived.

**Flash-Lite is the default, and not for speed.** Off the AI Studio rate-limit page
on 8 Oct: the full Flash models allow 5 requests a minute and 20 a DAY. Flash-Lite
allows 15 a minute and 500 a day. One agent turn costs several calls, so on a Flash
model the hosted app stops answering after three or four visitors. We tripped the
3.8 Flash ceiling with nothing but a benchmark and one test.
"""
from __future__ import annotations

import json
import os
import random
import re
import time

import requests

from . import cache

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"


class LLM:
    def __init__(self, provider: str | None = None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "mock")).lower()

    @property
    def model_name(self) -> str:
        if self.provider == "gemini":
            return os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        return self.provider

    def complete(self, system: str, user: str) -> str:
        """One-shot question in, text out. No tools."""
        if self.provider == "mock":
            return _mock(system, user)
        content = self.generate([_user(user)], system=system)
        return text_of(content)

    def generate(self, contents: list[dict], *, system: str | None = None,
                 tools: list[dict] | None = None) -> dict:
        """Run one turn and return the model's `content` VERBATIM.

        Give it the whole conversation so far. What comes back goes straight into
        `contents` for the next turn with nothing rebuilt — see the note at the top
        about thought signatures.
        """
        if self.provider == "mock":
            return {"role": "model", "parts": [{"text": _mock(system or "", _last_text(contents))}]}
        if self.provider != "gemini":
            raise NotImplementedError(
                f"LLM_PROVIDER={self.provider!r} isn't wired up. Use mock or gemini."
            )
        return _gemini(contents, system, tools, self.model_name)


def _user(text: str) -> dict:
    return {"role": "user", "parts": [{"text": text}]}


def text_of(content: dict) -> str:
    return "".join(p.get("text", "") for p in content.get("parts", [])).strip()


def calls_in(content: dict) -> list[dict]:
    """Any function calls the model asked for this turn. Empty means it's done."""
    return [p["functionCall"] for p in content.get("parts", []) if "functionCall" in p]


def _last_text(contents: list[dict]) -> str:
    for turn in reversed(contents):
        for part in turn.get("parts", []):
            if "text" in part:
                return part["text"]
    return ""


def _gemini(contents: list[dict], system: str | None,
            tools: list[dict] | None, model: str) -> dict:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("LLM_PROVIDER=gemini but there's no GEMINI_API_KEY in .env")

    body: dict = {"contents": contents,
                  "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if tools:
        body["tools"] = tools
        # AUTO lets the model decide whether to call something or just answer. ANY
        # would force a call every turn and the loop would never finish.
        body["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO"}}

    # Caching the exact request means a repeat question is instant and answers the
    # same way twice, which the demo recording depends on. LLM_NO_CACHE=1 skips it.
    ck = json.dumps([model, system, tools, contents], sort_keys=True, default=str)
    if not os.getenv("LLM_NO_CACHE"):
        hit = cache.get("gemini", ck)
        if hit:
            return hit

    failures: list[str] = []
    for candidate in _model_chain(model):
        for attempt in range(3):
            try:
                r = requests.post(ENDPOINT % candidate, json=body,
                                  headers={"x-goog-api-key": key}, timeout=60)
            except requests.RequestException:
                failures.append(f"{candidate} timeout")
                _backoff(attempt)
                continue

            if r.status_code < 400:
                data = r.json()
                try:
                    content = data["candidates"][0]["content"]
                except (KeyError, IndexError) as exc:
                    # Usually a blocked response, or it hit the output cap.
                    raise RuntimeError(
                        f"Couldn't read Gemini's reply: {json.dumps(data)[:300]}") from exc
                cache.put("gemini", ck, content)
                return content

            failures.append(f"{candidate} {r.status_code}")
            if r.status_code == 429 and _is_daily(r.text):
                # The day's quota is gone. Retrying this model is pointless, and
                # every attempt may cost us another request against it.
                break
            if r.status_code in (429, 503):
                _backoff(attempt)
                continue
            break  # 400, 403 and 404 won't fix themselves

    raise RuntimeError("Gemini wouldn't answer. Tried: " + ", ".join(failures))


def _backoff(attempt: int) -> None:
    # 1s, 2s, 4s with jitter, which is what Google's own troubleshooting page asks for.
    time.sleep(2 ** attempt + random.uniform(0, 0.5))


def _is_daily(body: str) -> bool:
    low = body.lower()
    return "perday" in low.replace("_", "") or "daily" in low


def _model_chain(preferred: str) -> list[str]:
    # Ordered by daily quota, not latency. Flash-Lite gets 500 requests a day
    # against 20 for the full Flash models, which matters far more than the
    # second or two of extra speed Flash gives you.
    #
    # Left out, and why, measured 8 Oct against this key:
    #   gemini-2.5-flash / -flash-lite / -pro   404, withdrawn for keys made recently
    #   gemini-flash-latest, gemini-pro-latest  429 on a first call, quota spent.
    #                                           They are aliases and get hot-swapped,
    #                                           so pin real ids instead.
    #   gemini-3.7-flash, gemini-3.5-flash      503 more often than not
    #   gemini-3-flash-preview                  answers, but took 19s
    chain = [preferred, "gemini-3.1-flash-lite", "gemini-3.6-flash"]
    seen, out = set(), []
    for m in chain:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


# --- mock -------------------------------------------------------------------
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
            "genres": [], "films": [],
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
    return chr(10).join(lines)


def _capitalised_names(text: str) -> list[str]:
    """Crude stand-in for entity extraction: grab the Capitalised Words."""
    skip = {"I", "Delhi", "Mumbai", "Saturday", "Sunday", "Friday"}
    found = re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b", text)
    return [f for f in found if f not in skip][:3]
