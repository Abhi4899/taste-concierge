# Build plan — Qloo LLM Hackathon

**Deadline:** 30 Oct 2026, 11:45pm EDT. **Today:** build has ~3.5 weeks.
**Goal:** a sharp, judge-friendly agentic demo that uses Qloo deeply, plus a 2–3 min video.

## What judges reward (from the laptop-only research)
- Deep, obvious use of the **sponsor API** (Qloo), not novelty.
- A **clear demo** (a 2–3 min video + live/CLI run) and a clean README + architecture.
- Far fewer people *submit* than register — finishing is most of the battle.

## Milestones

| By | Milestone |
|---|---|
| Day 1–2 | Register on the Qloo hackathon page; get the API key + read Qloo's API docs. Fill the `# TODO(qloo)` endpoints in `src/qloo_client.py`. |
| Day 3–5 | Replace MOCK with live Qloo calls. Confirm seed-resolution and insights work for 3 real taste prompts. |
| Day 6–8 | Wire a real LLM (Gemini free tier) for seed extraction + itinerary. Tighten prompts so every pick cites its Qloo source. |
| Day 9–12 | Add one "wow" feature: e.g. a tiny web UI, or multi-city support, or a "surprise me" cross-domain jump (music → film → restaurant). |
| Day 13–15 | Polish README + architecture diagram. Record the demo video. Final test. |
| By 30 Oct | Submit on Devpost (repo link + video + description). |

## Scope discipline
Keep it small and working. One clean agentic loop that demonstrably uses Qloo beats a sprawling half-finished app. The MOCK mode stays in so the demo never breaks live on stage.

## Cost control ($20 plan, no API budget)
- Use Gemini's **free tier** as the reasoning engine (already supported in `src/llm.py` over REST).
- Qloo API is provided by the hackathon.
- Claude Pro is your *build* tool, not a runtime cost.
