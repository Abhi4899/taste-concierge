# Throwaway smoke test: proves Streamlit Cloud can reach Qloo with our key.
# Not the real UI.
import os
import sys
import time

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


def get_key():
    # st.secrets raises if there's no secrets.toml at all, which is the normal
    # case locally, so fall back to .env.
    try:
        return st.secrets["QLOO_API_KEY"]
    except (KeyError, FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return os.getenv("QLOO_API_KEY", "")


st.title("Qloo smoke test")
st.caption(f"Python {sys.version.split()[0]} · Streamlit {st.__version__}")

key = get_key()
if not key:
    st.error("No QLOO_API_KEY in st.secrets or the environment.")
    st.stop()

city = st.text_input("City", "Delhi")

if st.button("Call Qloo"):
    params = {
        "filter.type": "urn:entity:place",
        # Place queries need a category, otherwise Qloo returns malls and museums.
        "filter.tags": "urn:tag:genre:place:restaurant",
        "filter.location.query": city,
        "take": 10,
    }
    started = time.perf_counter()
    r, error = None, None
    # Qloo times out often enough that one failure proves nothing.
    for attempt in range(1, 4):
        try:
            r = requests.get("https://hackathon.api.qloo.com/v2/insights", params=params,
                             headers={"X-Api-Key": key}, timeout=30)
            break
        except requests.RequestException as exc:
            error = exc
    elapsed = time.perf_counter() - started

    if r is None:
        st.error(f"No response after 3 attempts ({elapsed:.1f}s): {error}")
        st.stop()

    st.write(f"HTTP {r.status_code} in {elapsed:.1f}s (attempt {attempt})")
    if r.ok:
        results = r.json().get("results", {})
        entities = results.get("entities", []) if isinstance(results, dict) else results
        st.markdown("\n".join(f"- {e.get('name')}" for e in entities) or "No entities returned.")
    else:
        st.code(r.text[:500])
