"""The agent loop.

The model is given the Qloo tools and left to work out what to call. It decides
which tastes need resolving, which domains are worth asking about for this
particular request, whether a thin result is worth another try with different
arguments, and when it has enough to answer. None of that is scripted here.

That matters beyond tidiness: the hackathon treats "agentic" as a pass/fail gate
checked before anything is scored. A fixed sequence of calls with a model writing
the prose at the end does not clear it, which is what the previous version was.

Every turn is recorded in a trace, both because it is the evidence that the model
is really choosing, and because it makes a wrong turn obvious when the output
looks odd.
"""
from __future__ import annotations

import json
import os

from . import tools
from .llm import LLM, calls_in, text_of

MAX_TURNS = int(os.getenv("AGENT_MAX_TURNS", "8"))

SYSTEM = """You recommend culture and places using the Qloo taste graph.

Work out for yourself what to look up. A rough order that usually works: turn the
names and categories the person gave you into Qloo ids, then ask for whatever
domains suit what they actually asked for. Someone planning a night out wants
places; someone asking what to watch does not.

Judgement you are expected to use:
- Ask only for domains this person would care about. Don't sweep every one.
- A category is required on any place query, and the right one depends on the
  occasion. Drinks with friends is not the same as a quiet dinner.
- If a lookup finds nothing, try it differently rather than carrying on. A cuisine
  or a genre needs find_tag; only proper names go to resolve_taste.
- If results come back thin or obviously wrong, say so in your answer instead of
  pretending otherwise.
- Stop as soon as you have enough. More calls is not better.

When you are done, write the recommendations grouped by domain. One line per pick
saying which of their tastes it connects to. Only use names that came back from a
tool. Never quote affinity numbers; they are not comparable between calls and
reading them as percentages is wrong. Do not lay the answer out as a timetable or
an itinerary."""


def run(prompt: str, llm: LLM | None = None, max_turns: int = MAX_TURNS) -> dict:
    """Answer a request, letting the model drive. Returns the text and the trace."""
    llm = llm or LLM()
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    trace: list[dict] = []

    for turn in range(max_turns):
        content = llm.generate(contents, system=SYSTEM, tools=tools.DECLARATIONS)
        # Append verbatim. Gemini rejects the next turn if the thought signature
        # on a function-call part goes missing.
        contents.append(content)

        wanted = calls_in(content)
        if not wanted:
            return {"text": text_of(content), "trace": trace,
                    "turns": turn + 1, "tool_calls": len(trace)}

        results = []
        for call in wanted:
            args = call.get("args") or {}
            result = tools.run(call["name"], args)
            trace.append({"turn": turn + 1, "tool": call["name"], "args": args,
                          "summary": _summarise(result)})
            results.append({"functionResponse": {"name": call["name"],
                                                 "response": {"result": result}}})
        contents.append({"role": "user", "parts": results})

    # Out of turns. Ask for an answer with the tools taken away so it has to stop.
    content = llm.generate(contents, system=SYSTEM)
    return {"text": text_of(content), "trace": trace,
            "turns": max_turns, "tool_calls": len(trace), "hit_limit": True}


def _summarise(result: dict) -> str:
    """One line per call, for the audit panel."""
    if "error" in result:
        return f"error: {result['error'][:80]}"
    if "count" in result:
        names = [r.get("name") for r in result.get("results", [])[:3] if r.get("name")]
        return f"{result['count']} results" + (f": {', '.join(names)}" if names else "")
    if result.get("found"):
        return result.get("qloo_id") or result.get("tag_id") or "found"
    return "not found"


def describe(result: dict) -> str:
    """Readable trace, for the CLI."""
    lines = [f"{len(result['trace'])} tool calls over {result['turns']} turns"]
    for step in result["trace"]:
        args = json.dumps(step["args"], default=str)
        lines.append(f"  [{step['turn']}] {step['tool']}({args[:70]}) -> {step['summary']}")
    return chr(10).join(lines)
