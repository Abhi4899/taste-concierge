"""CLI. Mainly a harness for driving the agent without a UI in the way.

    python -m src.cli "I like qawwali and Kashmiri food, friends in Delhi"
    python -m src.cli --trace "..."      also prints every Qloo call it chose to make
"""
from __future__ import annotations

import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .core import loop, qloo
from .core.llm import LLM

DEFAULT = "I like qawwali and Kashmiri food, going out with friends in Delhi"


def main(argv: list[str]) -> int:
    args = argv[1:]
    trace = "--trace" in args
    prompt = " ".join(a for a in args if a != "--trace").strip() or DEFAULT

    llm = LLM()
    print(f"qloo={'mock' if qloo.MOCK else 'live'}  llm={llm.model_name}")
    print(f"> {prompt}")
    print("-" * 60)

    result = loop.run(prompt, llm=llm)
    print(result["text"])

    if trace:
        print("-" * 60)
        print(loop.describe(result))
    if result.get("hit_limit"):
        print("\n(note: the agent ran out of turns before it was finished)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
