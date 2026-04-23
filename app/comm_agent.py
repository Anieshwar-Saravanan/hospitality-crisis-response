"""
Communications Agent — powered by Gemini API (google-genai)
------------------------------------------------------------
Gemini decides EVERYTHING:
  • Which responders are needed based on incident type and required_services
  • The incident summary
  • Tailored dispatch message per responder unit
  • Minimum 3 units dispatched, more when warranted

Install:
    pip install streamlit networkx matplotlib google-genai

Run:
    streamlit run app.py
"""

import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import math, time, json, os, re
from dotenv import load_dotenv

load_dotenv()

# ── Gemini SDK ───────────────────────────────────────────────────────────────
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title="Comms Agent", page_icon="🚨", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Rajdhani', sans-serif;
    background-color: #0d0f14;
    color: #e0e6f0;
}
h1, h2, h3 { font-family: 'Share Tech Mono', monospace; }
.stApp { background-color: #0d0f14; }

section[data-testid="stSidebar"] {
    background-color: #111520;
    border-right: 1px solid #1e2a3a;
}
.block-container { padding-top: 2rem; }

div[data-testid="stTextArea"] textarea {
    background-color: #111520 !important;
    color: #7efff5 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 13px !important;
    border: 1px solid #1e3a52 !important;
    border-radius: 4px !important;
}
div[data-testid="stTextInput"] input {
    background-color: #111520 !important;
    color: #c0d8f0 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 13px !important;
    border: 1px solid #1e3a52 !important;
}
div.stButton > button {
    background: linear-gradient(135deg, #c0392b, #e74c3c);
    color: white;
    font-family: 'Share Tech Mono', monospace;
    font-size: 15px; font-weight: bold; letter-spacing: 2px;
    border: none; border-radius: 4px; padding: 0.6rem 2rem; width: 100%;
    box-shadow: 0 0 12px rgba(231,76,60,0.4);
}
div.stButton > button:hover {
    box-shadow: 0 0 22px rgba(231,76,60,0.7);
}
.alert-box {
    background: #12191f; border-left: 4px solid #e74c3c; border-radius: 4px;
    padding: 1rem 1.4rem; margin-bottom: 0.8rem;
    font-family: 'Share Tech Mono', monospace; color: #f8c6c2; font-size: 14px;
    box-shadow: 0 0 12px rgba(231,76,60,0.15);
}
.gemini-box {
    background: #0c1a10; border-left: 4px solid #27ae60; border-radius: 4px;
    padding: 1rem 1.4rem; margin-bottom: 0.8rem;
    font-family: 'Share Tech Mono', monospace; color: #a8f0c0; font-size: 13px;
    box-shadow: 0 0 10px rgba(39,174,96,0.12);
}
.msg-row {
    background: #0f161d; border: 1px solid #1e2f40; border-radius: 4px;
    padding: 0.6rem 1rem; margin-bottom: 0.5rem;
    font-family: 'Share Tech Mono', monospace; font-size: 12px; color: #8ecae6;
    line-height: 1.8;
}
.msg-row span.sent      { color: #2ecc71; font-weight: bold; }
.msg-row span.node-name { color: #f0c060; font-size: 13px; }
.stat-card {
    background: #111520; border: 1px solid #1e2a3a; border-radius: 6px;
    padding: 0.9rem 1.2rem; text-align: center;
}
.stat-num   { font-size: 2rem; font-family: 'Share Tech Mono', monospace; font-weight: bold; }
.stat-label { font-size: 12px; color: #607080; letter-spacing: 1px; }
.tag-gemini {
    display: inline-block; background: #0c1a10; border: 1px solid #27ae60;
    color: #2ecc71; font-family: 'Share Tech Mono', monospace;
    font-size: 10px; padding: 1px 8px; border-radius: 3px; margin-left: 6px;
    vertical-align: middle;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# MOCK RESPONDER DATA — 18 units across 7 service types
# ─────────────────────────────────────────────
RESPONDERS = [
    # Fire stations
    {"name": "Fire Stn Alpha",    "type": "fire",         "lat": 13.06, "lng": 80.24},
    {"name": "Fire Stn Bravo",    "type": "fire",         "lat": 13.10, "lng": 80.29},
    {"name": "Fire Stn Delta",    "type": "fire",         "lat": 13.04, "lng": 80.31},
    # Police
    {"name": "Police Post-1",     "type": "police",       "lat": 13.09, "lng": 80.26},
    {"name": "Police Post-2",     "type": "police",       "lat": 13.07, "lng": 80.22},
    {"name": "Police Post-3",     "type": "police",       "lat": 13.12, "lng": 80.28},
    # Hospitals
    {"name": "City Hospital",     "type": "hospital",     "lat": 13.08, "lng": 80.30},
    {"name": "Metro Med Ctr",     "type": "hospital",     "lat": 13.05, "lng": 80.25},
    {"name": "Apollo Clinic",     "type": "hospital",     "lat": 13.11, "lng": 80.23},
    # Ambulances
    {"name": "Ambulance Unit-1",  "type": "ambulance",    "lat": 13.07, "lng": 80.27},
    {"name": "Ambulance Unit-2",  "type": "ambulance",    "lat": 13.09, "lng": 80.24},
    {"name": "Ambulance Unit-3",  "type": "ambulance",    "lat": 13.05, "lng": 80.26},
    # Rescue teams
    {"name": "Rescue Team Alpha", "type": "rescue",       "lat": 13.06, "lng": 80.28},
    {"name": "Rescue Team Bravo", "type": "rescue",       "lat": 13.11, "lng": 80.26},
    # HazMat
    {"name": "HazMat Unit-1",     "type": "hazmat",       "lat": 13.08, "lng": 80.22},
    {"name": "HazMat Unit-2",     "type": "hazmat",       "lat": 13.06, "lng": 80.30},
    # Water Rescue
    {"name": "Water Rescue-1",    "type": "water_rescue", "lat": 13.05, "lng": 80.29},
    {"name": "Water Rescue-2",    "type": "water_rescue", "lat": 13.10, "lng": 80.30},
]

NODE_COLORS = {
    "fire":         "#e67e22",
    "police":       "#3498db",
    "hospital":     "#2ecc71",
    "ambulance":    "#1abc9c",
    "rescue":       "#9b59b6",
    "hazmat":       "#e74c3c",
    "water_rescue": "#5dade2",
    "llm":          "#c0392b",
}

TYPE_LABELS = {
    "fire":         "Fire Station",
    "police":       "Police",
    "hospital":     "Hospital",
    "ambulance":    "Ambulance",
    "rescue":       "Rescue Team",
    "hazmat":       "HazMat Unit",
    "water_rescue": "Water Rescue",
}

TYPE_EMOJI = {
    "fire":         "🔥",
    "police":       "🚔",
    "hospital":     "🏥",
    "ambulance":    "🚑",
    "rescue":       "🔭",
    "hazmat":       "☣️",
    "water_rescue": "🌊",
}

DEFAULT_JSON = """{
  "incident_type": "fire",
  "severity": "high",
  "location": {
    "lat": 13.08,
    "lng": 80.27,
    "address": "Anna Nagar",
    "city": "Chennai"
  },
  "casualties": { "trapped": 5, "injured": 0 },
  "required_services": ["fire brigade", "rescue", "ambulance"]
}"""

# ─────────────────────────────────────────────
# GEMINI SYSTEM PROMPT — fixed service routing
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are an AI emergency communications agent responsible for dispatching the CORRECT units to an emergency.

You receive:
1. A JSON incident report with incident_type, severity, location (lat/lng), and required_services.
2. A list of available responders, each with name, type, lat, lng.

## STEP 1 — Identify needed responder types from required_services
Use this mapping (keyword → responder type):
  fire / fire brigade              → fire
  ambulance / ems / medical        → ambulance
  hospital / trauma / casualty     → hospital
  police / law enforcement         → police
  rescue / search and rescue / sar → rescue
  hazmat / chemical / toxic / gas  → hazmat
  flood / water / water rescue / coast guard / water distribution → water_rescue

⚠️ CRITICAL RULES:
- A water shortage, flood, or water distribution incident does NOT need fire units.
- Only select "fire" type responders when required_services explicitly includes "fire" or "fire brigade".
- Only select types that appear in required_services. Never add extra types not requested.
- If required_services is missing, infer from incident_type: fire→fire+ambulance, flood→water_rescue+rescue+ambulance, medical→ambulance+hospital, crime→police+ambulance.

## STEP 2 — Select closest unit per needed type
For each required type, compute Euclidean distance from incident lat/lng to each responder of that type.
Select the single closest unit per type.

## STEP 3 — Meet the 3-unit minimum
Count total selected units. If fewer than 3:
  - Add the second-closest unit from the most critical service type already selected.
  - Repeat until total ≥ 3.

## STEP 4 — Output
Return ONLY this exact JSON with no markdown fences or extra text:
{
  "summary": "<concise 1-sentence incident summary>",
  "selected": [
    {
      "name": "<exact responder name from the provided list>",
      "type": "<responder type>",
      "distance_km": <float>,
      "reason": "<one sentence: why this specific unit>",
      "message": "<tailored dispatch message for this unit's role>"
    }
  ]
}"""

# ─────────────────────────────────────────────
# GEMINI API CALL
# ─────────────────────────────────────────────
def extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass
    brace = re.search(r"\{[\s\S]*\}", text)
    if brace:
        try:
            return json.loads(brace.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse JSON from Gemini.\n\nRaw response:\n{text[:1500]}")


def call_gemini(api_key: str, incident: dict) -> dict:
    client = genai.Client(api_key=api_key)

    prompt = f"""Incident report:
{json.dumps(incident, indent=2)}

Available responders ({len(RESPONDERS)} units):
{json.dumps(RESPONDERS, indent=2)}

Analyze the required_services and coordinates, then return your JSON dispatch decision."""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return extract_json(response.text)


def _incident_field(incident: dict, *keys):
    """Read a field trying multiple key names (handles both simple and triage JSON)."""
    for k in keys:
        v = incident.get(k)
        if v is not None:
            return v
    return None


# ─────────────────────────────────────────────
# GRAPH DRAWING
# ─────────────────────────────────────────────
def draw_graph(selected_nodes: list, edges_to_show: list):
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.patch.set_facecolor("#0d0f14")
    ax.set_facecolor("#0d0f14")

    G = nx.DiGraph()
    G.add_node("GEMINI\nAGENT", ntype="llm")
    for n in selected_nodes:
        G.add_node(n["name"], ntype=n["type"])
    for src, dst in edges_to_show:
        G.add_edge(src, dst)

    pos = {"GEMINI\nAGENT": (0, 0)}
    total = max(len(selected_nodes), 1)
    for i, n in enumerate(selected_nodes):
        angle = 2 * math.pi * i / total
        pos[n["name"]] = (math.cos(angle) * 2.6, math.sin(angle) * 2.6)

    node_colors = [NODE_COLORS.get(G.nodes[n]["ntype"], "#888888") for n in G.nodes]
    node_sizes  = [2000 if G.nodes[n]["ntype"] == "llm" else 1300 for n in G.nodes]

    nx.draw_networkx_nodes(G, pos, node_color=node_colors,
                           node_size=node_sizes, alpha=0.93, ax=ax)
    nx.draw_networkx_labels(G, pos, font_color="white",
                            font_size=7.5, font_family="monospace", ax=ax)
    if edges_to_show:
        nx.draw_networkx_edges(
            G, pos, edgelist=edges_to_show,
            edge_color="#e74c3c", arrows=True,
            arrowstyle="-|>", arrowsize=20,
            width=2.2, ax=ax,
            connectionstyle="arc3,rad=0.08",
        )

    # Dynamic legend — only types present in this dispatch + LLM
    present_types = {"llm"} | {n["type"] for n in selected_nodes}
    legend_handles = [
        mpatches.Patch(color=NODE_COLORS["llm"], label="Gemini Agent")
    ] + [
        mpatches.Patch(color=NODE_COLORS[t], label=TYPE_LABELS.get(t, t.title()))
        for t in sorted(present_types - {"llm"})
        if t in NODE_COLORS
    ]
    ax.legend(handles=legend_handles, loc="lower right",
              facecolor="#111520", edgecolor="#1e2a3a",
              labelcolor="white", fontsize=8)
    ax.axis("off")
    plt.tight_layout()
    return fig


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if "dispatch_result" not in st.session_state:
    st.session_state.dispatch_result = None
if "dispatch_incident" not in st.session_state:
    st.session_state.dispatch_incident = None

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚨 COMMS AGENT")
    st.markdown("<span class='tag-gemini'>Gemini 2.5 Flash</span>", unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("**Gemini API Key**")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        st.success("Gemini API key loaded from .env")
    else:
        st.warning("Set GEMINI_API_KEY in .env to dispatch.")
    st.markdown("---")

    st.markdown("**Triage JSON Input**")
    incoming_triage = st.session_state.get("shared_triage_json", DEFAULT_JSON)
    raw_json = st.text_area("", value=incoming_triage, height=230,
                             label_visibility="collapsed")
    dispatch_btn = st.button("⚡ DISPATCH")

    st.markdown("---")
    st.markdown("""
    <div style='font-size:11px;color:#445566;font-family:monospace;line-height:1.9'>
    Gemini will:<br>
    🧠 Read required_services from triage<br>
    📋 Write the incident summary<br>
    🎯 Pick closest unit per service type<br>
    📡 Dispatch minimum 3 units<br>
    ☣️ Never send fire to water emergencies<br><br>
    18 units · 7 service types<br>
    Severities: low / medium / high / critical
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
st.markdown("# COMMUNICATIONS AGENT")
st.markdown(
    "<p style='color:#445566;font-family:monospace;margin-top:-12px'>"
    "LLM-driven Emergency Dispatch &nbsp;·&nbsp; Gemini 2.5 Flash &nbsp;·&nbsp; 18 units · 7 service types"
    "</p>",
    unsafe_allow_html=True,
)

col_graph, col_log = st.columns([3, 2], gap="large")

graph_ph = col_graph.empty()
log_ph   = col_log.empty()

# Idle state
with graph_ph:
    st.pyplot(draw_graph([], []))
    plt.close()

with log_ph:
    st.markdown(
        "<div style='color:#334455;font-family:monospace;font-size:13px;padding:2rem 0'>"
        "↑ Set GEMINI_API_KEY in .env, enter JSON, click DISPATCH</div>",
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────
# DISPATCH FLOW
# ─────────────────────────────────────────────
if dispatch_btn:

    if not GENAI_AVAILABLE:
        st.error("Missing dependency. Run:  pip install google-genai")
        st.stop()

    if not api_key:
        st.error("Set GEMINI_API_KEY in .env before dispatching.")
        st.stop()

    try:
        incident = json.loads(raw_json)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        st.stop()

    # ── Call Gemini ──────────────────────────
    with st.spinner("🧠 Gemini is analysing required services and selecting responders..."):
        try:
            result = call_gemini(api_key.strip(), incident)
        except json.JSONDecodeError as e:
            st.error(f"Gemini returned malformed JSON: {e}")
            st.stop()
        except Exception as e:
            st.error(f"Gemini API error: {e}")
            st.stop()

    summary  = result.get("summary", "No summary.")
    selected = result.get("selected", [])

    if not selected:
        st.warning("Gemini returned no responders. Check your API key or JSON.")
        st.stop()

    # Store to session state for services dashboard
    st.session_state.dispatch_result   = result
    st.session_state.dispatch_incident = incident

    # ── Stats row ────────────────────────────
    sev  = (_incident_field(incident, "severity") or "?").upper()
    itype = (_incident_field(incident, "incident_type", "type") or "?").upper()
    people = _incident_field(incident, "people") or (
        (incident.get("casualties") or {}).get("trapped", 0) +
        (incident.get("casualties") or {}).get("injured", 0)
    ) or 0

    st.markdown("---")
    s1, s2, s3, s4 = st.columns(4)
    vals = [
        (sev,          "SEVERITY",         "#e74c3c"),
        (itype,        "INCIDENT TYPE",    "#e67e22"),
        (people,       "PEOPLE INVOLVED",  "#3498db"),
        (len(selected), "UNITS DISPATCHED", "#2ecc71"),
    ]
    for col, (val, label, color) in zip([s1, s2, s3, s4], vals):
        col.markdown(
            f'<div class="stat-card">'
            f'<div class="stat-num" style="color:{color}">{val}</div>'
            f'<div class="stat-label">{label}</div></div>',
            unsafe_allow_html=True,
        )

    # ── Alert + Gemini reasoning note ────────
    col_graph.markdown(
        f'<div class="alert-box">🚨 ALERT: {summary}</div>',
        unsafe_allow_html=True,
    )
    col_graph.markdown(
        f'<div class="gemini-box">🤖 <b>Gemini selected</b> {len(selected)} units '
        f'matched to required services across {len(RESPONDERS)} available responders.</div>',
        unsafe_allow_html=True,
    )

    # ── Animate edges + dispatch log ─────────
    edges_so_far = []
    log_lines    = []

    for node in selected:
        edges_so_far.append(("GEMINI\nAGENT", node["name"]))

        with graph_ph:
            st.pyplot(draw_graph(selected, edges_so_far))
            plt.close()

        emoji    = TYPE_EMOJI.get(node["type"], "📡")
        dist     = node.get("distance_km", "?")
        dist_str = f"{dist:.1f} km" if isinstance(dist, (int, float)) else f"{dist} km"

        log_lines.append(
            f'<div class="msg-row">'
            f'{emoji} → <span class="node-name">{node["name"]}</span>'
            f' &nbsp;<span style="color:#445566;font-size:11px">({dist_str})</span><br>'
            f'<span style="color:#4a7090;font-size:11px">💡 {node.get("reason", "")}</span><br>'
            f'<span style="color:#6090a8">{node.get("message", "")}</span><br>'
            f'<span class="sent">✔ DISPATCHED</span>'
            f'</div>'
        )

        with log_ph:
            st.markdown(
                "**DISPATCH LOG** <span class='tag-gemini'>AI-generated</span>",
                unsafe_allow_html=True,
            )
            st.markdown("".join(log_lines), unsafe_allow_html=True)

        time.sleep(1.2)

    col_log.success(f"✅ Gemini dispatched {len(selected)} units successfully.")

    st.markdown("---")
    if st.button("🖥️ View Services Dashboard", use_container_width=False):
        st.switch_page("services_dashboard.py")
