"""Taste Concierge, hosted.

Deliberately thin. Everything that thinks lives in src/core; this file only collects
a prompt and renders what comes back.

One ordering trap: src.core.qloo reads QLOO_API_KEY at import time, so the secrets
have to be in the environment before the import below, not after.
"""
import os
import sys

import streamlit as st

st.set_page_config(page_title="Taste Concierge", page_icon="*", layout="centered")


def _bridge_secrets() -> None:
    """Copy Streamlit secrets into the environment so src/core can read them.

    Locally there is usually no secrets.toml at all and st.secrets raises, so fall
    back to whatever .env already put in the environment.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    # Keys only. GEMINI_MODEL is deliberately not read from secrets: which model we
    # use is a measured decision that belongs in version control, and a stale secret
    # quietly overriding it is how the hosted app ended up running a model with a
    # 20-a-day quota while the code said something else entirely.
    for name in ("QLOO_API_KEY", "GEMINI_API_KEY"):
        try:
            value = st.secrets[name]
        except Exception:
            continue
        if value:
            os.environ[name] = str(value)
    os.environ.pop("GEMINI_MODEL", None)
    # On the hosted app there is a real key, so use a real model.
    if os.getenv("GEMINI_API_KEY") and not os.getenv("LLM_PROVIDER"):
        os.environ["LLM_PROVIDER"] = "gemini"


_bridge_secrets()

from src.core import qloo            # noqa: E402  (must follow _bridge_secrets)
from src.core.agent import recommend  # noqa: E402
from src.core.llm import LLM          # noqa: E402

EXAMPLES = [
    "I like qawwali and Kashmiri food, going out with friends in Delhi",
    "Big fan of Wong Kar-wai films and Vietnamese food, an evening in Mumbai",
    "I listen to John Coltrane and want somewhere to drink in London",
]

st.title("Taste Concierge")
st.caption("Tell it what you love. Qloo's taste graph finds the rest.")

with st.expander("Before you type anything, please read this"):
    st.markdown(
        "This runs on the **free tier of the Google Gemini API**. Under Google's API terms, "
        "anything you enter and anything the model replies is used to improve Google's "
        "products, and **human reviewers may read it**.\n\n"
        "So: please don't enter personal, confidential or sensitive information. Tastes and a "
        "city are all it needs.\n\n"
        "The free tier is also not licensed for users in the EEA, Switzerland or the UK, and "
        "is intended for people aged 18 or over.\n\n"
        "Venue and culture data comes from the [Qloo](https://qloo.com) Taste AI API."
    )

if "prompt" not in st.session_state:
    st.session_state.prompt = EXAMPLES[0]

st.write("Try one of these:")
cols = st.columns(len(EXAMPLES))
for col, example in zip(cols, EXAMPLES):
    label = example.split(",")[0]
    if col.button(label, use_container_width=True):
        st.session_state.prompt = example

prompt = st.text_area("What do you like?", key="prompt", height=90)
go = st.button("Find things I'd like", type="primary")

if go:
    if not prompt.strip():
        st.warning("Tell it something you like first.")
        st.stop()
    try:
        with st.spinner("Asking Qloo..."):
            result = recommend(prompt, trace=True)
    except Exception as exc:
        # Free-tier quota and Qloo timeouts both surface here. Say which, plainly,
        # rather than showing a stack trace to whoever is looking.
        st.error(f"{type(exc).__name__}: {exc}")
        st.stop()

    st.markdown(result["text"])

    trail, results = result["resolved"], result["results"]
    calls = len(trail) + len(results)
    with st.expander(f"What Qloo was asked — {calls} calls, {len(trail)} tastes resolved"):
        if trail:
            st.write("**Resolved to Qloo entities and tags**")
            st.dataframe(
                [{"from": t.get("from"), "name": t.get("name"), "qloo id": t.get("qloo_id")}
                 for t in trail],
                use_container_width=True, hide_index=True)
        for domain, rows in results.items():
            st.write(f"**{domain.replace('_', ' ')}** — {len(rows)} results")
            st.dataframe(
                [{"name": r.get("name"), "area": r.get("neighborhood"),
                  "tags": ", ".join(r.get("tags") or [])[:60]} for r in rows],
                use_container_width=True, hide_index=True)
        st.caption(
            "Affinity scores are left out on purpose. Qloo returns them per call and they "
            "aren't comparable between calls, so showing them implies a precision that "
            "isn't there."
        )

st.divider()
st.caption(
    f"qloo: {'mock' if qloo.MOCK else 'live'} · model: {LLM().model_name} · "
    f"python {sys.version.split()[0]}"
)
