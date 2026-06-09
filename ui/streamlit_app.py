"""Admin UI for the Review Intelligence Tool.

A separate Streamlit app that drives the existing Flask API over HTTP. It does
not import or modify the core project: everything goes through the public
endpoints, so the API stays the single source of behaviour. Run the Flask app
first (see README), then `streamlit run ui/streamlit_app.py`.
"""

import json
import os
import subprocess
import time
from pathlib import Path

import requests
import streamlit as st

DEFAULT_BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:5000")
RUNFILE = Path(__file__).resolve().parent.parent / "data" / "ui_pids.json"
STRICTNESS_LEVELS = ["strict", "standard", "loose"]
STRICTNESS_HELP = (
    "How demanding the relevance gate is for this topic. "
    "strict: review must name the company/product and give pros and cons. "
    "standard: must plausibly concern the topic. "
    "loose: any genuine review with at least one positive or negative point."
)

st.set_page_config(page_title="Review Intelligence - Admin", layout="wide")


def _base():
    return st.session_state.get("base_url", DEFAULT_BASE).rstrip("/")


def api_get(path):
    return requests.get(_base() + path, timeout=60)


def api_post(path, payload=None):
    return requests.post(_base() + path, json=payload or {}, timeout=180)


def show_error(resp):
    """Render an API error response in a way that distinguishes the gate's 422
    rejection (a normal, explained outcome) from other failures."""
    try:
        body = resp.json()
    except ValueError:
        body = {"error": resp.text}
    reason = body.get("error", "Unknown error")
    if resp.status_code == 422 and body.get("rejected"):
        st.warning(f"Rejected by the validation gate ({resp.status_code}): {reason}")
    else:
        st.error(f"{resp.status_code}: {reason}")


@st.cache_data(ttl=5)
def fetch_topics(base):
    resp = requests.get(base + "/topics", timeout=60)
    resp.raise_for_status()
    return resp.json()


def topic_options(base):
    topics = fetch_topics(base)
    labels = {t["id"]: f'{t["id"]} - {t["name"]} [{t["relevance_strictness"]}]' for t in topics}
    return topics, labels


def shutdown_app():
    """Stop the API, then stop this UI process. Same effect as the stop link.

    When started by run_ui.py the API pid is recorded in the runfile; otherwise
    fall back to whatever is listening on the API port.
    """
    api_pid = None
    if RUNFILE.exists():
        try:
            api_pid = json.loads(RUNFILE.read_text()).get("api")
        except (ValueError, OSError):
            api_pid = None
    if api_pid:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(api_pid)], capture_output=True)
    else:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if "LISTENING" in line and ":5000" in line:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", line.split()[-1]], capture_output=True
                )
    # Stop this UI process last; this ends the Streamlit server we run inside.
    os._exit(0)


# --- sidebar -------------------------------------------------------------
st.sidebar.title("Review Intelligence")
st.session_state.setdefault("base_url", DEFAULT_BASE)
st.session_state["base_url"] = st.sidebar.text_input("API base URL", st.session_state["base_url"])

if st.sidebar.button("Check connection"):
    try:
        r = api_get("/topics")
        st.sidebar.success(f"Connected ({r.status_code}), {len(r.json())} topics")
    except Exception as e:
        st.sidebar.error(f"Cannot reach API: {e}")

st.sidebar.caption("This UI is a separate client; all actions go through the Flask API.")

st.sidebar.divider()
if st.sidebar.button("Shut down app", key="shutdown_btn", help="Stops the API and closes the UI."):
    st.sidebar.warning("Shutting down. You can close this tab.")
    time.sleep(1.0)
    shutdown_app()

topics_tab, reviews_tab, evaluate_tab, agent_tab = st.tabs(
    ["Topics", "Reviews", "Evaluate", "Agent chat"]
)

# --- Topics --------------------------------------------------------------
with topics_tab:
    st.subheader("Topics")
    try:
        topics = fetch_topics(_base())
        st.dataframe(topics, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Could not load topics: {e}")

    st.markdown("**Create a topic**")
    with st.form("create_topic"):
        name = st.text_input("Name")
        col1, col2 = st.columns(2)
        category = col1.selectbox("Category", ["(none)", "company", "product", "service"])
        strictness = col2.selectbox(
            "Relevance strictness", STRICTNESS_LEVELS, index=1, help=STRICTNESS_HELP
        )
        created_by = st.text_input("Created by", value="admin")
        submitted = st.form_submit_button("Create topic")
    if submitted:
        payload = {
            "name": name,
            "category": None if category == "(none)" else category,
            "created_by": created_by or None,
            "relevance_strictness": strictness,
        }
        resp = api_post("/topics", payload)
        if resp.status_code == 201:
            st.success(f"Created topic {resp.json()['id']}")
            fetch_topics.clear()
            st.rerun()
        else:
            show_error(resp)

# --- Reviews -------------------------------------------------------------
with reviews_tab:
    st.subheader("Reviews")
    try:
        topics, labels = topic_options(_base())
    except Exception as e:
        topics, labels = [], {}
        st.error(f"Could not load topics: {e}")

    if not topics:
        st.info("Create a topic first.")
    else:
        topic_id = st.selectbox(
            "Topic", list(labels), format_func=lambda i: labels[i], key="reviews_topic"
        )
        with st.form("add_review"):
            review_text = st.text_area("Review text")
            source = st.text_input("Source", value="manual")
            add = st.form_submit_button("Submit review")
        if add:
            resp = api_post(
                "/reviews",
                {"topic_id": topic_id, "review_text": review_text, "source": source or None},
            )
            if resp.status_code == 201:
                st.success("Review accepted and stored.")
            else:
                show_error(resp)

        st.markdown("**Stored reviews**")
        try:
            r = api_get(f"/topics/{topic_id}/reviews")
            data = r.json()
            st.caption(f"{len(data)} review(s)")
            st.dataframe(data, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Could not load reviews: {e}")

# --- Evaluate ------------------------------------------------------------
with evaluate_tab:
    st.subheader("Run an evaluation")
    try:
        topics, labels = topic_options(_base())
    except Exception as e:
        topics, labels = [], {}
        st.error(f"Could not load topics: {e}")

    if not topics:
        st.info("Create a topic with some reviews first.")
    else:
        topic_id = st.selectbox(
            "Topic", list(labels), format_func=lambda i: labels[i], key="eval_topic"
        )
        if st.button("Evaluate topic"):
            resp = api_post(f"/topics/{topic_id}/evaluate")
            if resp.status_code == 200:
                data = resp.json()
                ev = data["evaluation"]
                c1, c2, c3 = st.columns(3)
                c1.metric("Sentiment", ev["overall_sentiment"])
                c2.metric("Rating", f'{ev["rating"]}/5')
                c3.metric("Reviews", data["review_count"])
                st.write(f'**Summary.** {ev["short_summary"]}')
                st.write(ev["long_summary"])
                st.write("**Key themes:** " + ", ".join(ev["key_themes"]))
                st.caption(
                    f'model {data["model"]} | {data["prompt_technique"]} | '
                    f'{data["latency_ms"]} ms | ${data["total_cost"]:.6f}'
                )
            else:
                show_error(resp)

# --- Agent chat ----------------------------------------------------------
with agent_tab:
    st.subheader("Evaluation Agent")
    thread_id = st.text_input("Thread id", value="ui-thread-1")
    st.session_state.setdefault("chat_history", {})
    history = st.session_state["chat_history"].setdefault(thread_id, [])

    if st.button("Clear this thread's transcript"):
        history.clear()
        st.rerun()

    for turn in history:
        with st.chat_message(turn["role"]):
            st.write(turn["content"])

    prompt = st.chat_input("Ask the agent to evaluate a topic by id or name")
    if prompt:
        history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
        resp = api_post(f"/v2/chat/{thread_id}", {"message": prompt})
        if resp.status_code == 200:
            data = resp.json()
            reply = data.get("reply") or "(no reply)"
            history.append({"role": "assistant", "content": reply})
            with st.chat_message("assistant"):
                st.write(reply)
                verified = data.get("verified_topic_id")
                if verified is not None:
                    st.caption(f"Verified topic on this thread: {verified}")
        else:
            show_error(resp)
