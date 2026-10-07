"""Thin LLM wrapper. Gemini over REST, plus a mock so the CLI runs without any key.

REST rather than the SDK on purpose: two fewer dependencies, and all we need is one POST.
"""
from __future__ import annotations

import json
import os
import re
import time

import requests

from . import cache


class LLM:
    def __init__(self, provider: str | None = None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "mock")).lower()

    @property
    def model_name(self) -> str:
        if self.provider == "gemini":
            return os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
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

    # Cached so a repeated question is instant and gives the same answer twice.
    # That matters for the demo: a recorded walkthrough shouldn't depend on whether
    # the free tier feels like answering. Set LLM_NO_CACHE=1 to bypass.
    cache_key = chr(10).join([model, system, user])
    if not os.getenv("LLM_NO_CACHE"):
        hit = cache.get("gemini", cache_key)
        if hit:
            return hit

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
                text = "".join(p.get("text", "") for p in parts).strip()
                if text:
                    cache.put("gemini", cache_key, text)
                return text

            failures.append(f"{candidate} -> {r.status_code}")
            if r.status_code in (429, 503):
                time.sleep(2 ** attempt)
                continue
            break  # 400s and 404s won't fix themselves

    raise RuntimeError("Gemini wouldn't answer. Tried: " + ", ".join(failures))


def _model_chain(preferred: str) -> list[str]:
    # Measured against this key on 8 Oct 2026, fastest usable first. Everything
    # here answered a real request; the ones left out did not:
    #   gemini-2.5-flash / -flash-lite / -pro  404, gone for keys created recently
    #   gemini-flash-latest, gemini-pro-latest 429, their shared quota was spent
    #   gemini-3.7-flash, gemini-3.5-flash     503, busy more often than not
    #   gemini-3-flash-preview                 works but took 19s
    chain = [preferred, "gemini-flash-lite-latest", "gemini-3.5-flash-lite",
             "gemini-3.1-flash-lite", "gemini-3.8-flash"]
    seen, out = set(), []
    for m in chain:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out
