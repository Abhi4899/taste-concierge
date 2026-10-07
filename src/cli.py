"""CLI. Mainly a harness for poking at the engine without a UI in the way.

    python -m src.cli "I like qawwali and Kashmiri food, going out with friends in Delhi"
    python -m src.cli --trace "..."      also dumps every Qloo result it used
"""
from __future__ import annotations

import json
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from .core import qloo
from .core.agent import recommend
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

    result = recommend(prompt, llm=llm, trace=trace)
    if trace:
        print(result["text"])
        print("-" * 60)
        print(json.dumps({k: v for k, v in result.items() if k != "text"},
                         indent=2, default=str))
    else:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
