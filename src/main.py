"""CLI entry point.

Usage:
    python -m src.main "I love Radiohead and Korean food, plan a Saturday in Delhi"

Runs in MOCK mode with no API keys set, so it always produces output for a demo.
"""
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional; env vars still work if set another way

from .agent import plan_outing
from . import qloo_client
from .llm import LLM


def main(argv: list[str]) -> int:
    prompt = " ".join(argv[1:]).strip() or (
        "I love Radiohead and Korean food, plan a Saturday in Delhi"
    )
    mode = "MOCK" if qloo_client.MOCK else "LIVE"
    print(f"[taste-concierge] Qloo: {mode} | LLM: {LLM().provider}\n")
    print(f"Request: {prompt}\n{'-' * 60}")
    print(plan_outing(prompt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
