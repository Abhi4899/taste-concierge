"""Does the agent actually decide anything, or is it a fixed pipeline in disguise?

The hackathon checks "agentic" as a pass/fail gate before it scores anything else,
so this is the test that matters most. It runs several different requests and
compares the tool calls each one produced. If every request drives the same calls
in the same order, the model is not choosing and we have not cleared the gate,
whatever the README claims.

    python -m scripts.gate_check   (or run the file directly)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.core import loop
from src.core.llm import LLM

PROMPTS = [
    "I like qawwali and Kashmiri food, going out with friends in Delhi",
    "What should I watch tonight? I love Wong Kar-wai and Radiohead.",
    "I listen to John Coltrane and want somewhere to drink in London",
    "Quiet cafe in Mumbai to read in. I like Murakami.",
]


def main() -> int:
    llm = LLM()
    if llm.provider == "mock":
        print("LLM_PROVIDER is mock, so there is nothing to decide. Set it to gemini.")
        return 1

    shapes = []
    for prompt in PROMPTS:
        print("=" * 72)
        print(prompt)
        print("=" * 72)
        try:
            result = loop.run(prompt, llm=llm)
        except Exception as exc:
            print(f"  FAILED: {type(exc).__name__}: {exc}")
            shapes.append(None)
            continue

        print(loop.describe(result))
        print()
        print("  " + (result["text"][:260].replace("\n", "\n  ") or "(no text)"))
        print()
        shapes.append(tuple(step["tool"] for step in result["trace"]))

    print("=" * 72)
    print("VERDICT")
    print("=" * 72)
    for prompt, shape in zip(PROMPTS, shapes):
        print(f"  {prompt[:46]:<46} {list(shape) if shape else 'failed'}")

    usable = [s for s in shapes if s]
    if len(usable) < 2:
        print("\n  INCONCLUSIVE: too few runs completed.")
        return 1

    distinct = len(set(usable))
    lengths = {len(s) for s in usable}
    print(f"\n  distinct call sequences : {distinct} of {len(usable)}")
    print(f"  distinct call counts    : {sorted(lengths)}")

    if distinct == 1:
        print("\n  FAIL. Every request produced the same calls in the same order.")
        print("  That is a fixed pipeline with a model narrating it. Fix before the UI.")
        return 1
    print("\n  PASS. Different requests drove different tool use, so the model is")
    print("  choosing. Keep this output; it is the evidence for the gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
