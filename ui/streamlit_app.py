"""Admin dashboard for the Review Intelligence Tool.

A separate Streamlit app that drives the existing Flask API over HTTP. It does
not import or change the core project; everything goes through the public
endpoints. The look follows design/dashboard-mockup-4.html: dark canvas, violet
accent, KPI cards, a verdict strip, an "Ask the agent" hero band, charts, and a
reviews feed. SVG icons replace the older glyph set.

The visual panels are rendered as HTML so the design matches the mockup; the
interactive parts (topic picker, forms, agent input, chips, buttons) are
Streamlit widgets. The agent band is a keyed st.container so the native chat
widgets live inside the styled panel.
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

# One-tap starter questions for the agent (label shown on the chip, prompt sent).
AGENT_CHIPS = [
    ("Biggest problem?", "What is the single biggest problem here?"),
    ("Anything positive?", "Is there anything positive in these reviews?"),
    ("Top 3 themes", "What are the top three recurring themes?"),
    ("One-line summary", "Summarise the overall sentiment in one line."),
]

# Lucide-style inline SVGs (stroke = currentColor via .ic).
IC = {
    "smile": '<svg class="ic" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M8 15s1.5-2 4-2 4 2 4 2M9 9h.01M15 9h.01"/></svg>',
    "star": '<svg class="ic" viewBox="0 0 24 24"><path d="M12 3l2.9 5.9 6.1.9-4.5 4.3 1 6-5.5-2.9L6.5 21l1-6L3 9.8l6.1-.9z"/></svg>',
    "list": '<svg class="ic" viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h10"/></svg>',
    "alert": '<svg class="ic" viewBox="0 0 24 24"><path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17h.01"/></svg>',
    "verdict": '<svg class="ic" viewBox="0 0 24 24"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="9"/></svg>',
    "donut": '<svg class="ic" viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 10 10"/><path d="M12 12V2a10 10 0 0 1 10 10z"/></svg>',
    "bars": '<svg class="ic" viewBox="0 0 24 24"><path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/></svg>',
    "drivers": '<svg class="ic" viewBox="0 0 24 24"><path d="M7 11v9M7 11l4-7a2 2 0 0 1 3 2l-1 5h5a2 2 0 0 1 2 2.4l-1.5 6A2 2 0 0 1 16.5 22H7"/></svg>',
    "spark": '<svg class="ic" viewBox="0 0 24 24"><path d="M12 3l1.6 4.9L18.5 9.5 13.6 11 12 16l-1.6-5L5.5 9.5l4.9-1.6z"/><path d="M19 14l.7 2.1L22 17l-2.3.9L19 20l-.7-2.1L16 17l2.3-.9z"/></svg>',
}

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
  .block-container{ padding-top:1.6rem; padding-bottom:3rem; max-width:1200px; }
  [data-testid="stSidebar"]{ background:#101227; border-right:1px solid rgba(255,255,255,.07); }
  [data-testid="stSidebar"] * { color:#c7cbe6; }

  svg.ic{ width:1em;height:1em;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;display:inline-block;vertical-align:-.14em }

  .ri-brand{ display:flex;align-items:center;gap:10px;font-weight:800;font-size:16px;color:#fff;margin-bottom:6px }
  .ri-brand .logo{ width:30px;height:30px;border-radius:9px;display:grid;place-items:center;font-size:13px;
       background:linear-gradient(135deg,#8b5cff,#ff5cb0);box-shadow:0 6px 18px rgba(139,92,255,.45) }

  .ri-h1{ font-size:24px;font-weight:800;color:#eef0fb;margin:0;letter-spacing:-.01em }
  .ri-sub{ color:#8b90b5;font-size:13px;margin:3px 0 16px;display:flex;align-items:center;gap:8px }
  .ri-sub .live{ display:inline-flex;align-items:center;gap:6px;color:#2dd4a7 }
  .ri-sub .live i{ width:7px;height:7px;border-radius:50%;background:#2dd4a7;animation:pulse 2s infinite }
  @keyframes pulse{ 0%{box-shadow:0 0 0 0 rgba(45,212,167,.5)}70%{box-shadow:0 0 0 7px rgba(45,212,167,0)}100%{box-shadow:0 0 0 0 rgba(45,212,167,0)} }

  .sec-h{ display:flex;align-items:center;gap:9px;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#5d628a;margin:26px 2px 12px }
  .sec-h .ln{ flex:1;height:1px;background:linear-gradient(90deg,rgba(255,255,255,.10),transparent) }

  .ri-verdict{ display:flex;align-items:center;justify-content:space-between;gap:18px;margin:0 0 4px;
       background:linear-gradient(120deg,rgba(139,92,255,.18),rgba(255,92,176,.08));
       border:1px solid rgba(139,92,255,.30);border-radius:14px;padding:15px 20px }
  .ri-verdict .vl{ display:flex;align-items:center;gap:14px }
  .ri-verdict .tag{ flex:none;display:inline-flex;align-items:center;gap:6px;font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;font-weight:800;
       color:#ffd0ea;background:rgba(255,92,176,.16);padding:6px 11px;border-radius:20px }
  .ri-verdict .vt{ font-size:14px;color:#e7e9fb;line-height:1.45 } .ri-verdict .vt b{ color:#fff }
  .ri-verdict .vr{ flex:none;display:flex;align-items:center;gap:9px;font-weight:700;font-size:15px;color:#fff;white-space:nowrap }

  .ri-row{ display:flex;gap:16px;margin-bottom:16px } .ri-row > *{ flex:1 }
  .ri-card{ background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.09);border-radius:16px;
       padding:18px 20px;backdrop-filter:blur(8px);transition:transform .16s ease,border-color .16s ease,background .16s ease }
  .ri-card:hover{ transform:translateY(-2px);border-color:rgba(255,255,255,.16);background:rgba(255,255,255,.07) }
  .ri-card h3{ margin:0 0 2px;font-size:14px;font-weight:700;color:#eef0fb;display:flex;align-items:center;gap:8px }
  .ri-card h3 .ic{ font-size:16px } .ri-card .hint{ color:#5d628a;font-size:12px;margin:0 0 14px }
  .kpi .top{ display:flex;align-items:center;justify-content:space-between;margin-bottom:12px }
  .kpi .icon{ width:36px;height:36px;border-radius:10px;display:grid;place-items:center;font-size:18px }
  .kpi .k{ font-size:27px;font-weight:800;line-height:1;color:#fff } .kpi .lbl{ color:#8b90b5;font-size:12.5px;margin-top:6px;display:flex;align-items:center;gap:6px }
  .stars{ color:#ffb84d;font-size:14px;letter-spacing:1px }
  .chip{ font-size:11px;font-weight:700;padding:4px 10px;border-radius:20px }
  .chip.neg{ background:rgba(255,92,122,.15);color:#ff5c7a } .chip.pos{ background:rgba(45,212,167,.15);color:#2dd4a7 }
  .chip.mix{ background:rgba(255,184,77,.15);color:#ffb84d }

  .ri-sum{ font-size:13.5px;color:#cfd2ee;line-height:1.55;margin:0 }
  .ri-rev{ display:flex;gap:12px;padding:13px 0;border-top:1px solid rgba(255,255,255,.08) }
  .ri-rev:first-child{ border-top:none;padding-top:2px }
  .ri-rev .av{ width:36px;height:36px;border-radius:50%;flex:none;display:grid;place-items:center;color:#fff;font-weight:700;font-size:14px }
  .ri-rev .who{ font-weight:600;font-size:13.5px;color:#eef0fb } .ri-rev .meta{ color:#5d628a;font-size:11.5px;margin:1px 0 5px }
  .ri-rev p{ margin:0;font-size:13px;color:#bcc0e0;line-height:1.5 }

  .donut-wrap{ display:flex;align-items:center;gap:24px;margin-top:4px }
  .donut{ width:128px;height:128px;border-radius:50%;display:grid;place-items:center;position:relative;flex:none }
  .donut::after{ content:"";width:84px;height:84px;background:#11132a;border-radius:50% }
  .donut .dc{ position:absolute;text-align:center } .donut .dc b{ font-size:20px;font-weight:800;display:block;color:#fff } .donut .dc span{ font-size:10.5px;color:#8b90b5 }
  .legend{ display:flex;flex-direction:column;gap:10px;font-size:13px;color:#c7cbe6 }
  .legend .li{ display:flex;align-items:center;gap:9px } .legend .sw{ width:11px;height:11px;border-radius:3px } .legend b{ margin-left:auto;color:#fff }
  .bars{ display:flex;flex-direction:column;gap:10px;margin-top:4px }
  .bars .bar{ display:flex;align-items:center;gap:10px;font-size:12px;color:#8b90b5 }
  .bars .lab{ width:26px;text-align:right } .bars .val{ width:26px;text-align:right;color:#fff;font-weight:700 }
  .bars .track{ flex:1;height:9px;background:rgba(255,255,255,.07);border-radius:6px;overflow:hidden }
  .bars .fill{ height:100%;border-radius:6px;background:linear-gradient(90deg,#8b5cff,#ff5cb0) }
  .themebars{ display:flex;flex-direction:column;gap:12px;margin-top:2px }
  .themebars .th .h{ display:flex;justify-content:space-between;font-size:12.5px;font-weight:600;color:#eef0fb;margin-bottom:6px }
  .themebars .th .h span{ color:#5d628a;font-weight:500 }
  .themebars .th .track{ height:7px;background:rgba(255,255,255,.07);border-radius:6px;overflow:hidden }
  .themebars .th .fill{ height:100%;border-radius:6px }

  /* ===== Agent hero band (keyed container) ===== */
  .st-key-agent_hero{
    position:relative;border-radius:18px;padding:22px 24px 18px;margin-top:2px;
    background:linear-gradient(125deg,rgba(139,92,255,.22),rgba(255,92,176,.10) 70%);
    border:1px solid rgba(139,92,255,.45);
    box-shadow:0 0 0 1px rgba(139,92,255,.12),0 22px 55px rgba(139,92,255,.18);
  }
  .ah-head{ display:flex;align-items:center;gap:13px;margin-bottom:2px }
  .ah-ico{ width:42px;height:42px;border-radius:12px;flex:none;display:grid;place-items:center;color:#fff;font-size:21px;
       background:linear-gradient(135deg,#8b5cff,#ff5cb0);box-shadow:0 8px 22px rgba(139,92,255,.5) }
  .ah-title{ font-size:17px;font-weight:800;color:#fff;display:flex;align-items:center;gap:9px }
  .ah-title .ai{ font-size:9.5px;letter-spacing:.12em;text-transform:uppercase;font-weight:800;color:#ffd0ea;background:rgba(255,92,176,.18);padding:4px 9px;border-radius:20px }
  .ah-sub{ font-size:12.5px;color:#c9b8f5;margin:2px 0 0 }
  .thread{ display:flex;flex-direction:column;gap:10px;margin:16px 0 14px }
  .thread .bubble{ font-size:13px;line-height:1.5;padding:11px 15px;border-radius:14px;max-width:82% }
  .thread .bubble.u{ background:linear-gradient(135deg,rgba(139,92,255,.45),rgba(255,92,176,.32));color:#fff;margin-left:auto;border-bottom-right-radius:4px }
  .thread .bubble.a{ background:rgba(10,11,20,.45);color:#e3e5fb;border:1px solid rgba(255,255,255,.08);border-bottom-left-radius:4px }
  .thread .hint{ color:#b6a8e6;font-size:12.5px;margin:0 }
  .typing{ display:inline-flex;gap:5px;align-items:center;padding:13px 16px;border-radius:14px;background:rgba(10,11,20,.45);border:1px solid rgba(255,255,255,.08);border-bottom-left-radius:4px;width:max-content }
  .typing span{ width:7px;height:7px;border-radius:50%;background:#b9a6ff;animation:blink 1.4s infinite both }
  .typing span:nth-child(2){ animation-delay:.2s } .typing span:nth-child(3){ animation-delay:.4s }
  @keyframes blink{ 0%,80%,100%{opacity:.25}40%{opacity:1} }
  /* chip buttons inside the band */
  .st-key-agent_hero .stButton>button{ background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.14);color:#e7e3fb;
       border-radius:20px;font-weight:600;font-size:12.5px;padding:6px 12px;transition:all .15s }
  .st-key-agent_hero .stButton>button:hover{ background:rgba(139,92,255,.28);border-color:rgba(139,92,255,.6);color:#fff;transform:translateY(-1px) }
  .st-key-agent_hero [data-testid="stChatInput"]{ background:rgba(10,11,20,.5);border:1px solid rgba(255,255,255,.16);border-radius:13px }
  .st-key-agent_hero [data-testid="stChatInput"]:focus-within{ border-color:rgba(139,92,255,.7);box-shadow:0 0 0 3px rgba(139,92,255,.2) }

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


SENT_COLOR = {"positive": "#2dd4a7", "negative": "#ff5c7a", "mixed": "#ffb84d", "neutral": "#8b90b5"}


def build_donut(counts):
    total = sum(counts.values()) or 1
    stops, acc, legend = [], 0.0, ""
    for name in ["negative", "mixed", "neutral", "positive"]:
        c = counts.get(name, 0)
        if not c:
            continue
        pct = c / total * 100
        stops.append(f"{SENT_COLOR[name]} {acc:.1f}% {acc + pct:.1f}%")
        acc += pct
        legend += (f'<div class="li"><span class="sw" style="background:{SENT_COLOR[name]}"></span>'
                   f'{name.capitalize()} <b>{round(pct)}%</b></div>')
    gradient = ", ".join(stops) or "#8b90b5 0 100%"
    dom = max(counts, key=lambda k: counts[k])
    dom_pct = round(counts.get(dom, 0) / total * 100)
    return (f'<div class="donut-wrap"><div class="donut" style="background:conic-gradient({gradient})">'
            f'<div class="dc"><b>{dom_pct}%</b><span>{esc(dom)}</span></div></div>'
            f'<div class="legend">{legend}</div></div>')


def build_rating_bars(counts):
    mx = max(counts.values()) or 1
    rows = ""
    for n in range(5, 0, -1):
        c = counts.get(str(n), 0)
        rows += (f'<div class="bar"><span class="lab">{n}&#9733;</span>'
                 f'<div class="track"><div class="fill" style="width:{c / mx * 100:.0f}%"></div></div>'
                 f'<span class="val">{c}</span></div>')
    return f'<div class="bars">{rows}</div>'


def build_theme_bars(items, color):
    if not items:
        return '<p class="hint">None identified.</p>'
    mx = max((i["count"] for i in items), default=1) or 1
    rows = ""
    for i in items[:5]:
        rows += (f'<div class="th"><div class="h">{esc(i["theme"])} <span>{i["count"]}</span></div>'
                 f'<div class="track"><div class="fill" style="width:{i["count"] / mx * 100:.0f}%;background:{color}"></div></div></div>')
    return f'<div class="themebars">{rows}</div>'


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


def create_topic_form(in_dialog=False):
    """Shared create-topic form, used by the sidebar modal and Manage data."""
    suffix = "_dlg" if in_dialog else ""
    with st.form("create_topic" + suffix):
        name = st.text_input("Name")
        cat = st.selectbox("Category", ["(none)", "company", "product", "service"], key="cat" + suffix)
        strict = st.selectbox("Relevance strictness", STRICTNESS_LEVELS, index=1, key="strict" + suffix,
                              help="strict: must name the topic with pros and cons. standard: must be on-topic. loose: any genuine review.")
        if st.form_submit_button("Create topic", type="primary"):
            if not name.strip():
                st.error("Name is required.")
                return
            resp = api_post("/topics", {"name": name, "category": None if cat == "(none)" else cat,
                                        "created_by": "admin", "relevance_strictness": strict})
            if resp.status_code == 201:
                fetch_topics.clear()
                st.toast(f"Created topic: {name}", icon="✅")
                st.rerun()
            else:
                try:
                    st.error(resp.json().get("error", resp.text))
                except ValueError:
                    st.error(resp.text)


@st.dialog("Create a topic")
def new_topic_dialog():
    st.caption("New topics start empty. Add reviews to them from Manage data.")
    create_topic_form(in_dialog=True)


# ----------------------------------------------------------------- sidebar
st.session_state.setdefault("base_url", DEFAULT_BASE)
st.session_state.setdefault("evals", {})
st.session_state.setdefault("breakdowns", {})
st.session_state.setdefault("chat", {})
st.session_state.setdefault("pending", {})

st.sidebar.markdown('<div class="ri-brand"><div class="logo">RI</div> Review Intelligence</div>', unsafe_allow_html=True)

try:
    topics = fetch_topics(_base())
    conn_ok = True
except Exception:
    topics, conn_ok = [], False
    st.sidebar.error(f"Cannot reach API at {_base()}")

view = st.sidebar.radio("View", ["Dashboard", "Manage data"], label_visibility="collapsed")

selected = None
if topics:
    labels = {t["id"]: f'{t["name"]} ({t["relevance_strictness"]})' for t in topics}
    sel_id = st.sidebar.selectbox("Topic", list(labels), format_func=lambda i: labels[i])
    selected = next(t for t in topics if t["id"] == sel_id)
else:
    st.sidebar.info("No topics yet. Create one below.")

if st.sidebar.button("➕  New topic", use_container_width=True, type="primary", disabled=not conn_ok):
    new_topic_dialog()

st.sidebar.divider()
if st.sidebar.button("Shut down app", use_container_width=True, help="Stops the API and closes the UI."):
    st.sidebar.warning("Shutting down. You can close this tab.")
    time.sleep(1.0)
    shutdown_app()


# ----------------------------------------------------------------- agent band
def render_agent(tid, tname):
    thread = f"dash-{tid}"
    hist = st.session_state["chat"].setdefault(thread, [])
    pending = st.session_state["pending"].get(thread)

    with st.container(key="agent_hero"):
        header = (
            f'<div class="ah-head"><div class="ah-ico">{IC["spark"]}</div>'
            f'<div><div class="ah-title">Ask the agent <span class="ai">AI</span></div>'
            f'<div class="ah-sub">Conversational evaluation over this topic. It remembers the thread and runs real evaluations.</div></div></div>'
        )
        bubbles = "".join(
            f'<div class="bubble {"u" if m["role"] == "user" else "a"}">{esc(m["content"])}</div>' for m in hist
        )
        if not hist and not pending:
            bubbles = '<p class="hint">Ask anything about this topic, or tap a starter question below.</p>'
        typing = '<div class="typing"><span></span><span></span><span></span></div>' if pending else ""
        st.markdown(f'{header}<div class="thread">{bubbles}{typing}</div>', unsafe_allow_html=True)

        cols = st.columns(len(AGENT_CHIPS))
        for col, (label, prompt) in zip(cols, AGENT_CHIPS):
            if col.button(label, key=f"chip_{tid}_{label}", use_container_width=True, disabled=bool(pending)):
                hist.append({"role": "user", "content": prompt})
                st.session_state["pending"][thread] = prompt
                st.rerun()

        q = st.chat_input("Ask anything about this topic...", disabled=bool(pending))
        if q:
            hist.append({"role": "user", "content": q})
            st.session_state["pending"][thread] = q
            st.rerun()

    # Process the pending turn after the thread (with the typing bubble) is drawn.
    if pending:
        try:
            r = api_post(f"/v2/chat/{thread}", {"message": pending})
            reply = r.json().get("reply", "(no reply)") if r.status_code == 200 else f"Error: {r.status_code}"
        except Exception as e:
            reply = f"Could not reach the agent: {e}"
        hist.append({"role": "assistant", "content": reply})
        st.session_state["pending"][thread] = None
        st.rerun()


# ----------------------------------------------------------------- dashboard
def render_dashboard(topic):
    tid, tname = topic["id"], topic["name"]

    try:
        reviews = api_get(f"/topics/{tid}/reviews").json()
    except Exception:
        reviews = []
    n_reviews = len(reviews)

    ev = st.session_state["evals"].get(tid)

    # topbar: title + sub on the left, Run evaluation on the right
    head_l, head_r = st.columns([7, 2])
    with head_l:
        st.markdown(f'<div class="ri-h1">{esc(tname)}</div>', unsafe_allow_html=True)
        evaluated = '<span class="live"><i></i> Evaluated</span> &middot; ' if ev else ""
        sub = f"{evaluated}{n_reviews} reviews stored &middot; strictness: {esc(topic['relevance_strictness'])}"
        if ev:
            sub += " &middot; gpt-4o-mini"
        st.markdown(f'<div class="ri-sub">{sub}</div>', unsafe_allow_html=True)
    with head_r:
        run = st.button("Run evaluation", type="primary", disabled=n_reviews == 0, use_container_width=True)
    if run:
        with st.spinner("Analyzing reviews..."):
            r = api_post(f"/topics/{tid}/evaluate")
            b = api_post(f"/topics/{tid}/breakdown")
        ok = True
        if r.status_code == 200:
            st.session_state["evals"][tid] = r.json()
        else:
            ok = False
            st.error(f"Evaluation failed: {r.text}")
        if b.status_code == 200:
            st.session_state["breakdowns"][tid] = b.json()
        elif r.status_code == 200:
            st.warning(f"Charts unavailable: {b.text}")
        if ok:
            st.rerun()

    ev = st.session_state["evals"].get(tid)
    bd = st.session_state["breakdowns"].get(tid)

    # verdict strip
    if ev:
        e = ev["evaluation"]
        st.markdown(
            f'''<div class="ri-verdict"><div class="vl">
              <span class="tag">{IC["verdict"]} Verdict</span>
              <span class="vt"><b>{esc(e["overall_sentiment"].capitalize())}.</b> {esc(e["short_summary"])}</span>
            </div><div class="vr"><span class="stars">{stars(e["rating"])}</span> {esc(e["rating"])}/5</div></div>''',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="ri-verdict"><div class="vl"><span class="tag">{IC["verdict"]} Verdict</span>'
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
          <div class="ri-card kpi"><div class="top"><div class="icon chip {sclass}">{IC["smile"]}</div><span class="chip {sclass}">{esc(sentiment_k)}</span></div>
            <div class="k">{esc(sentiment_k)}</div><div class="lbl">Overall sentiment</div></div>
          <div class="ri-card kpi"><div class="top"><div class="icon chip mix">{IC["star"]}</div></div>
            <div class="k">{rating_k}</div><div class="lbl">{rating_stars} Average rating</div></div>
          <div class="ri-card kpi"><div class="top"><div class="icon" style="background:rgba(139,92,255,.18);color:#8b5cff">{IC["list"]}</div></div>
            <div class="k">{n_reviews}</div><div class="lbl">Reviews stored</div></div>
          <div class="ri-card kpi"><div class="top"><div class="icon chip neg">{IC["alert"]}</div></div>
            <div class="k" style="font-size:17px;padding-top:5px">{esc(top_theme)}</div><div class="lbl">Top theme</div></div>
        </div>''',
        unsafe_allow_html=True,
    )

    # agent hero
    st.markdown('<div class="sec-h">Ask your data <span class="ln"></span></div>', unsafe_allow_html=True)
    render_agent(tid, tname)

    # breakdown charts
    if bd:
        st.markdown('<div class="sec-h">Breakdown <span class="ln"></span></div>', unsafe_allow_html=True)
        st.markdown(
            f'''<div class="ri-row">
              <div class="ri-card"><h3>{IC["donut"]} Sentiment breakdown</h3><p class="hint">Share of reviews by overall tone</p>{build_donut(bd["sentiment_counts"])}</div>
              <div class="ri-card"><h3>{IC["bars"]} Rating distribution</h3><p class="hint">How the {bd["review_count"]} reviews score the brand</p>{build_rating_bars(bd["rating_counts"])}</div>
            </div>
            <div class="ri-row">
              <div class="ri-card"><h3 style="color:#ff5c7a">{IC["alert"]} Top pain points</h3><p class="hint">Recurring negative themes</p>{build_theme_bars(bd["pain_points"], "#ff5c7a")}</div>
              <div class="ri-card"><h3 style="color:#2dd4a7">{IC["drivers"]} Positive drivers</h3><p class="hint">What happy customers mention</p>{build_theme_bars(bd["positive_drivers"], "#2dd4a7")}</div>
            </div>''',
            unsafe_allow_html=True,
        )

    # reviews feed (full width)
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
    st.markdown('<div class="sec-h">Recent reviews <span class="ln"></span></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ri-card"><p class="hint">Validated and stored under this topic</p>{rev_html}</div>', unsafe_allow_html=True)


# ----------------------------------------------------------------- manage
def render_manage(topic):
    st.markdown('<div class="ri-h1">Manage data</div><div class="ri-sub">Create topics and add reviews. Reviews pass the AI validation gate before they are stored.</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("##### Create a topic")
        create_topic_form()

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
        st.info("Create a topic to see the dashboard.")
else:
    render_manage(selected)
