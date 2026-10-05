# Project context for Claude Code

**What this is:** Taste Concierge — an agentic cultural outing planner built on Qloo's Taste AI API, for the Qloo LLM Hackathon (deadline 30 Oct 2026). Solo entry by a Delhi-based LLM developer.

**Hard constraints (from the owner):**
- Laptop + Claude only. No paid API budget — prefer free tiers (Gemini free key) or hackathon-provided credits.
- The repo is public (portfolio piece + hackathon open-source eligibility) — never commit secrets. Keys live in `.env` (gitignored); `.env.example` documents them.

**Architecture:** `src/main.py` (CLI) → `src/agent.py` (plan → tool calls → synthesize) → `src/qloo_client.py` (Qloo API wrapper, has MOCK mode) + `src/llm.py` (provider-agnostic LLM wrapper, has MOCK mode). The whole pipeline runs offline in MOCK mode so it's always demonstrable.

**Current state:** scaffold complete, runs in MOCK mode. Real wiring is marked `# TODO(qloo)` and `# TODO(llm)` — fill these once the hackathon API key and Qloo docs are available.

**Conventions:** keep it small and readable (judges read the repo). Match existing style. Every Qloo-driven pick in the output should cite the Qloo entity it came from — the point is "grounded in Qloo," not "LLM guessed."

**Build plan & submission checklist:** see `docs/BUILD_PLAN.md` and `docs/SUBMISSION_CHECKLIST.md`.
