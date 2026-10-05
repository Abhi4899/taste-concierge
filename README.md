# Taste Concierge

An agentic **cultural outing planner** built on [Qloo](https://qloo.com)'s Taste AI™ API.

You tell it what you're into — *"I love Radiohead and Korean food, plan a Saturday in Delhi"* — and an LLM-driven agent uses Qloo's cross-domain taste graph to find culturally-aligned restaurants, venues, music and films, then composes a concrete plan. It chains multiple tool calls (taste lookup → affinity expansion → local filtering → itinerary) rather than answering in one shot.

> Built for the **Qloo LLM Hackathon** (deadline **30 Oct 2026**). Solo entry.

## Why this is a good agentic demo

Qloo's API answers "what else do people who like X also like?" across music, dining, film, travel and more. That is exactly the kind of external knowledge an LLM *doesn't* have and shouldn't hallucinate — so wrapping Qloo as an agent tool is a clean, judge-friendly use of the sponsor API.

## How it works

```
User taste prompt
      │
      ▼
[1] LLM extracts "taste seeds"  ──►  e.g. {music: Radiohead, cuisine: Korean, city: Delhi}
      │
      ▼
[2] Qloo: resolve each seed to an entity id      (qloo_client.search_entity)
      │
      ▼
[3] Qloo: get cross-domain affinities / insights (qloo_client.get_insights)
      │
      ▼
[4] LLM composes an itinerary from the real Qloo results, citing each pick
      │
      ▼
Outing plan (with why-this-fits reasons)
```

## Quick start

```bash
# 1. create + activate a virtual environment (already set up as .venv)
.venv\Scripts\activate            # Windows PowerShell:  .venv\Scripts\Activate.ps1

# 2. install deps
pip install -r requirements.txt

# 3. copy the env template and add your keys
copy .env.example .env            # then edit .env

# 4. run it (works in MOCK mode with no keys, for a quick smoke test)
python -m src.main "I love Radiohead and Korean food, plan a Saturday in Delhi"
```

With no API keys set, the app runs in **MOCK mode** using sample data, so the pipeline is demonstrable offline. Add real keys in `.env` to hit the live Qloo API and a real LLM.

## Keys you'll need (see `.env.example`)

| Key | Where to get it | Notes |
|---|---|---|
| `QLOO_API_KEY` | Qloo hackathon portal (given on registration) | Confirm the live base URL + endpoints from Qloo's docs and update `src/qloo_client.py` |
| `LLM_PROVIDER` + its key | Gemini (free tier), Anthropic, or OpenAI | The agent's reasoning engine; a free Gemini key keeps cost at ₹0 |

## Status

Scaffold is complete and runs in MOCK mode. The real-API wiring (`# TODO(qloo)` markers in `src/qloo_client.py`) gets filled once the hackathon API key + docs are in hand.

## License

MIT — intentionally open so it's eligible for the hackathon's open-source scoring and usable as a public portfolio piece.
