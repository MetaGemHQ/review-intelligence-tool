"""Admin dashboard for the Review Intelligence Tool.

A separate Streamlit app that drives the existing Flask API over HTTP. It does
not import or change the core project; everything goes through the public
endpoints. The look follows design/dashboard-mockup-3.html: dark canvas, violet
accent, KPI cards, a verdict strip, key themes, a reviews feed, and the agent.

The visual panels are rendered as HTML so the design matches the mockup; the
interactive parts (topic picker, forms, agent input, buttons) are Streamlit
widgets. Charts that would need per-review sentiment are adapted to the
aggregate evaluation the API actually returns.
"""

import html
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
SENT_CLASS = {"positive": "pos", "negative": "neg", "mixed": "mix", "neutral": "mix"}

st.set_page_config(page_title="Review Intelligence", layout="wide", initial_sidebar_state="expanded")

CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
  html, body, [class*="css"], .stApp, [data-testid="stSidebar"] { font-family:'Inter',sans-serif; }
  #MainMenu, header[data-testid="stHeader"], footer { display:none !important; visibility:hidden; }
  .stDeployButton, [data-testid="stToolbar"] { display:none !important; }
  .stApp{
    background:#0a0b14;
    background-image:radial-gradient(900px 520px at 12% -8%,rgba(139,92,255,.20),transparent 60%),
                     radial-gradient(820px 520px at 100% 0%,rgba(255,92,176,.13),transparent 55%);
    background-attachment:fixed;
  }
  .block-container{ padding-top:1.6rem; padding-bottom:3rem; max-width:1280px; }
  [data-testid="stSidebar"]{ background:#101227; border-right:1px solid rgba(255,255,255,.07); }
  [data-testid="stSidebar"] * { color:#c7cbe6; }

  .ri-brand{ display:flex;align-items:center;gap:10px;font-weight:800;font-size:16px;color:#fff;margin-bottom:6px }
  .ri-brand .logo{ width:30px;height:30px;border-radius:9px;display:grid;place-items:center;font-size:13px;
       background:linear-gradient(135deg,#8b5cff,#ff5cb0);box-shadow:0 6px 18px rgba(139,92,255,.45) }

  .ri-h1{ font-size:23px;font-weight:800;color:#eef0fb;margin:0 }
  .ri-sub{ color:#8b90b5;font-size:13px;margin:2px 0 18px }

  .ri-verdict{ display:flex;align-items:center;justify-content:space-between;gap:18px;margin:0 0 18px;
       background:linear-gradient(120deg,rgba(139,92,255,.18),rgba(255,92,176,.08));
       border:1px solid rgba(139,92,255,.30);border-radius:14px;padding:14px 20px }
  .ri-verdict .vl{ display:flex;align-items:center;gap:14px }
  .ri-verdict .tag{ flex:none;font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;font-weight:800;
       color:#ffd0ea;background:rgba(255,92,176,.16);padding:5px 10px;border-radius:20px }
  .ri-verdict .vt{ font-size:14px;color:#e7e9fb;line-height:1.45 } .ri-verdict .vt b{ color:#fff }
  .ri-verdict .vr{ flex:none;display:flex;align-items:center;gap:9px;font-weight:700;font-size:14px;color:#fff;white-space:nowrap }

  .ri-row{ display:flex;gap:16px;margin-bottom:16px } .ri-row > *{ flex:1 }
  .ri-card{ background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.09);border-radius:16px;
       padding:18px 20px;backdrop-filter:blur(8px) }
  .ri-card h3{ margin:0 0 2px;font-size:14px;font-weight:600;color:#eef0fb } .ri-card .hint{ color:#5d628a;font-size:12px;margin:0 0 14px }
  .kpi .top{ display:flex;align-items:center;justify-content:space-between;margin-bottom:12px }
  .kpi .icon{ width:34px;height:34px;border-radius:10px;display:grid;place-items:center;font-size:15px }
  .kpi .k{ font-size:26px;font-weight:800;line-height:1;color:#fff } .kpi .lbl{ color:#8b90b5;font-size:12.5px;margin-top:6px }
  .stars{ color:#ffb84d;font-size:14px;letter-spacing:1px }
  .chip{ font-size:11px;font-weight:700;padding:4px 10px;border-radius:20px }
  .chip.neg{ background:rgba(255,92,122,.15);color:#ff5c7a } .chip.pos{ background:rgba(45,212,167,.15);color:#2dd4a7 }
  .chip.mix{ background:rgba(255,184,77,.15);color:#ffb84d }

  .ri-themes{ display:flex;flex-wrap:wrap;gap:8px }
  .ri-themes .t{ font-size:12.5px;font-weight:600;color:#d4d7f0;background:rgba(255,255,255,.06);
       border:1px solid rgba(255,255,255,.08);padding:7px 12px;border-radius:20px }
  .ri-sum{ font-size:13.5px;color:#cfd2ee;line-height:1.55;margin:0 }
  .ri-sum .short{ color:#fff;font-weight:600;display:block;margin-bottom:8px }

  .ri-rev{ display:flex;gap:12px;padding:13px 0;border-top:1px solid rgba(255,255,255,.08) }
  .ri-rev:first-child{ border-top:none;padding-top:2px }
  .ri-rev .av{ width:34px;height:34px;border-radius:50%;flex:none;display:grid;place-items:center;color:#fff;font-weight:700;font-size:13px }
  .ri-rev .who{ font-weight:600;font-size:13px;color:#eef0fb } .ri-rev .meta{ color:#5d628a;font-size:11px;margin:1px 0 5px }
  .ri-rev p{ margin:0;font-size:12.5px;color:#bcc0e0;line-height:1.5 }

  .ri-bub{ font-size:13px;line-height:1.5;padding:10px 14px;border-radius:13px;max-width:88%;margin-bottom:9px }
  .ri-bub.u{ background:linear-gradient(135deg,rgba(139,92,255,.32),rgba(255,92,176,.24));color:#f3eefe;margin-left:auto;border-bottom-right-radius:4px }
  .ri-bub.a{ background:rgba(255,255,255,.06);color:#d4d7f0;border-bottom-left-radius:4px }
  .stButton>button{ border-radius:10px;font-weight:600 }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------- helpers
def _base():
    return st.session_state.get("base_url", DEFAULT_BASE).rstrip("/")


def api_get(path):
    return requests.get(_base() + path, timeout=60)


def api_post(path, payload=None):
    return requests.post(_base() + path, json=payload or {}, timeout=180)


@st.cache_data(ttl=5)
def fetch_topics(base):
    r = requests.get(base + "/topics", timeout=60)
    r.raise_for_status()
    return r.json()


def esc(s):
    return html.escape(str(s if s is not None else ""))


def stars(rating):
    try:
        n = int(round(float(rating)))
    except (TypeError, ValueError):
        n = 0
    n = max(0, min(5, n))
    return "&#9733;" * n + "&#9734;" * (5 - n)


def shutdown_app():
    """Stop the API, then stop this UI process (same effect as the stop link)."""
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
                subprocess.run(["taskkill", "/F", "/T", "/PID", line.split()[-1]], capture_output=True)
    os._exit(0)


# ----------------------------------------------------------------- sidebar
st.session_state.setdefault("base_url", DEFAULT_BASE)
st.session_state.setdefault("evals", {})
st.session_state.setdefault("chat", {})

st.sidebar.markdown('<div class="ri-brand"><div class="logo">RI</div> Review Intelligence</div>', unsafe_allow_html=True)

try:
    topics = fetch_topics(_base())
    conn_ok = True
except Exception as e:
    topics, conn_ok = [], False
    st.sidebar.error(f"Cannot reach API at {_base()}")

view = st.sidebar.radio("View", ["Dashboard", "Manage data"], label_visibility="collapsed")

selected = None
if topics:
    labels = {t["id"]: f'{t["name"]} ({t["relevance_strictness"]})' for t in topics}
    sel_id = st.sidebar.selectbox("Topic", list(labels), format_func=lambda i: labels[i])
    selected = next(t for t in topics if t["id"] == sel_id)
else:
    st.sidebar.info("No topics yet. Create one in Manage data.")

st.sidebar.divider()
if st.sidebar.button("Shut down app", use_container_width=True, help="Stops the API and closes the UI."):
    st.sidebar.warning("Shutting down. You can close this tab.")
    time.sleep(1.0)
    shutdown_app()


# ----------------------------------------------------------------- dashboard
def render_dashboard(topic):
    tid, tname = topic["id"], topic["name"]
    st.markdown(f'<div class="ri-h1">{esc(tname)}</div>', unsafe_allow_html=True)

    try:
        reviews = api_get(f"/topics/{tid}/reviews").json()
    except Exception:
        reviews = []
    n_reviews = len(reviews)

    ev = st.session_state["evals"].get(tid)
    sub = f"{n_reviews} reviews stored &middot; strictness: {esc(topic['relevance_strictness'])}"
    if ev:
        sub += " &middot; evaluated with gpt-4o-mini"
    st.markdown(f'<div class="ri-sub">{sub}</div>', unsafe_allow_html=True)

    cols = st.columns([2, 6])
    if cols[0].button("Run evaluation", type="primary", disabled=n_reviews == 0, use_container_width=True):
        with st.spinner("Evaluating reviews..."):
            r = api_post(f"/topics/{tid}/evaluate")
        if r.status_code == 200:
            st.session_state["evals"][tid] = r.json()
            st.rerun()
        else:
            try:
                st.error(r.json().get("error", r.text))
            except ValueError:
                st.error(r.text)
    ev = st.session_state["evals"].get(tid)

    # verdict strip
    if ev:
        e = ev["evaluation"]
        sclass = SENT_CLASS.get(e["overall_sentiment"], "mix")
        st.markdown(
            f'''<div class="ri-verdict"><div class="vl">
              <span class="tag">Verdict</span>
              <span class="vt"><b>{esc(e["overall_sentiment"].capitalize())}.</b> {esc(e["short_summary"])}</span>
            </div><div class="vr"><span class="stars">{stars(e["rating"])}</span> {esc(e["rating"])}/5</div></div>''',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="ri-verdict"><div class="vl"><span class="tag">Verdict</span>'
            '<span class="vt">Run an evaluation to generate the verdict for this topic.</span></div></div>',
            unsafe_allow_html=True,
        )

    # KPI row
    if ev:
        e = ev["evaluation"]
        sclass = SENT_CLASS.get(e["overall_sentiment"], "mix")
        top_theme = e["key_themes"][0] if e.get("key_themes") else "-"
        sentiment_k = e["overall_sentiment"].capitalize()
        rating_k = f'{e["rating"]}<span style="font-size:14px;color:#8b90b5">/5</span>'
        rating_stars = f'<span class="stars">{stars(e["rating"])}</span>'
    else:
        sclass, top_theme, sentiment_k, rating_k, rating_stars = "mix", "-", "-", "-", ""
    st.markdown(
        f'''<div class="ri-row">
          <div class="ri-card kpi"><div class="top"><div class="icon chip {sclass}">&#9786;</div><span class="chip {sclass}">{esc(sentiment_k)}</span></div>
            <div class="k">{esc(sentiment_k)}</div><div class="lbl">Overall sentiment</div></div>
          <div class="ri-card kpi"><div class="top"><div class="icon chip mix">&#9733;</div></div>
            <div class="k">{rating_k}</div><div class="lbl">{rating_stars} Average rating</div></div>
          <div class="ri-card kpi"><div class="top"><div class="icon" style="background:rgba(139,92,255,.18);color:#8b5cff">&#9776;</div></div>
            <div class="k">{n_reviews}</div><div class="lbl">Reviews stored</div></div>
          <div class="ri-card kpi"><div class="top"><div class="icon chip neg">&#9888;</div></div>
            <div class="k" style="font-size:17px;padding-top:5px">{esc(top_theme)}</div><div class="lbl">Top theme</div></div>
        </div>''',
        unsafe_allow_html=True,
    )

    # summary + themes
    if ev:
        e = ev["evaluation"]
        themes_html = "".join(f'<span class="t">{esc(t)}</span>' for t in e.get("key_themes", []))
        st.markdown(
            f'''<div class="ri-row">
              <div class="ri-card" style="flex:1.4"><h3>Summary</h3><p class="hint">What the reviews say overall</p>
                <p class="ri-sum"><span class="short">{esc(e["short_summary"])}</span>{esc(e["long_summary"])}</p></div>
              <div class="ri-card"><h3>Key themes</h3><p class="hint">Recurring topics across the reviews</p>
                <div class="ri-themes">{themes_html}</div></div>
            </div>''',
            unsafe_allow_html=True,
        )

    # reviews + agent
    palette = ["#ff5c7a", "#8b5cff", "#2dd4a7", "#ffb84d", "#36c5f0", "#ff5cb0"]
    rev_html = ""
    for i, r in enumerate(reviews[:6]):
        txt = r["review_text"]
        txt = txt if len(txt) <= 220 else txt[:217] + "..."
        who = (r.get("source") or "Review").strip()
        rev_html += (
            f'<div class="ri-rev"><div class="av" style="background:{palette[i % len(palette)]}">{esc(who[:1].upper())}</div>'
            f'<div><div class="who">{esc(who)}</div><div class="meta">{esc(r.get("submitted_at", ""))}</div>'
            f'<p>{esc(txt)}</p></div></div>'
        )
    if not rev_html:
        rev_html = '<p class="hint">No reviews yet. Add some in Manage data.</p>'

    left, right = st.columns([1, 1])
    with left:
        st.markdown(f'<div class="ri-card"><h3>Recent reviews</h3><p class="hint">Validated and stored under this topic</p>{rev_html}</div>', unsafe_allow_html=True)
    with right:
        thread = f"dash-{tid}"
        hist = st.session_state["chat"].setdefault(thread, [])
        bubbles = "".join(
            f'<div class="ri-bub {"u" if m["role"]=="user" else "a"}">{esc(m["content"])}</div>' for m in hist
        ) or '<p class="hint">Ask a question about this topic below.</p>'
        st.markdown(f'<div class="ri-card"><h3>Ask the agent</h3><p class="hint">Conversational evaluation over this topic</p>{bubbles}</div>', unsafe_allow_html=True)
        q = st.chat_input("Ask about this topic...")
        if q:
            hist.append({"role": "user", "content": q})
            r = api_post(f"/v2/chat/{thread}", {"message": q})
            reply = r.json().get("reply", "(no reply)") if r.status_code == 200 else f"Error: {r.status_code}"
            hist.append({"role": "assistant", "content": reply})
            st.rerun()


# ----------------------------------------------------------------- manage
def render_manage(topic):
    st.markdown('<div class="ri-h1">Manage data</div><div class="ri-sub">Create topics and add reviews. Reviews pass the AI validation gate before they are stored.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("##### Create a topic")
        with st.form("create_topic"):
            name = st.text_input("Name")
            cat = st.selectbox("Category", ["(none)", "company", "product", "service"])
            strict = st.selectbox("Relevance strictness", STRICTNESS_LEVELS, index=1,
                                  help="strict: must name the topic with pros and cons. standard: must be on-topic. loose: any genuine review.")
            if st.form_submit_button("Create topic", type="primary"):
                resp = api_post("/topics", {"name": name, "category": None if cat == "(none)" else cat,
                                            "created_by": "admin", "relevance_strictness": strict})
                if resp.status_code == 201:
                    st.success(f"Created topic {resp.json()['id']}")
                    fetch_topics.clear()
                else:
                    try:
                        st.error(resp.json().get("error", resp.text))
                    except ValueError:
                        st.error(resp.text)

    with c2:
        st.markdown("##### Add a review")
        if topic is None:
            st.info("Create a topic first.")
        else:
            st.caption(f"Adding to: {topic['name']} ({topic['relevance_strictness']})")
            with st.form("add_review"):
                text = st.text_area("Review text", height=160)
                source = st.text_input("Source", value="manual")
                if st.form_submit_button("Submit review", type="primary"):
                    resp = api_post("/reviews", {"topic_id": topic["id"], "review_text": text, "source": source or None})
                    if resp.status_code == 201:
                        st.success("Review accepted and stored.")
                    else:
                        try:
                            body = resp.json()
                        except ValueError:
                            body = {"error": resp.text}
                        if resp.status_code == 422:
                            st.warning(f"Rejected by the validation gate: {body.get('error', '')}")
                        else:
                            st.error(f"{resp.status_code}: {body.get('error', '')}")

    if topic is not None:
        st.divider()
        st.markdown(f"##### Reviews under {esc(topic['name'])}")
        try:
            data = api_get(f"/topics/{topic['id']}/reviews").json()
            st.caption(f"{len(data)} review(s)")
            st.dataframe(data, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"Could not load reviews: {e}")


# ----------------------------------------------------------------- route
if not conn_ok:
    st.error("The API is not reachable. Start it (run_ui) and refresh.")
elif view == "Dashboard":
    if selected:
        render_dashboard(selected)
    else:
        st.info("Create a topic in Manage data to see the dashboard.")
else:
    render_manage(selected)
