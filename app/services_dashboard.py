"""
Emergency Services Command Dashboard
--------------------------------------
Mock command-center view for all 7 service types.
Shows unit availability and active dispatch orders received from the Comms Agent.
"""

import streamlit as st
import json
from datetime import datetime, timezone

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Services Dashboard", page_icon="🖥️", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Barlow', sans-serif; }
.stApp { background: #080c10; color: #d0dce8; }
section[data-testid="stSidebar"] { background: #0c1018 !important; border-right: 1px solid #1a2a3a; }
h1, h2, h3 { font-family: 'Share Tech Mono', monospace !important; color: #5dade2 !important; letter-spacing: 0.06em; }

.unit-card {
    background: #0c1420; border: 1px solid #1a2a3a;
    border-radius: 8px; padding: 14px 16px; margin: 6px 0;
    font-family: 'Share Tech Mono', monospace; font-size: 0.82rem;
    position: relative; transition: border-color 0.2s;
}
.unit-card.dispatched {
    background: #100c08; border-color: #f0a500;
    box-shadow: 0 0 12px rgba(240,165,0,0.15);
}
.unit-card.available { border-color: #1e4a30; }

.unit-name   { font-size: 0.96rem; font-weight: 700; color: #d0dce8; margin-bottom: 4px; }
.unit-type   { font-size: 0.72rem; letter-spacing: 0.1em; text-transform: uppercase;
               display: inline-block; padding: 1px 8px; border-radius: 3px; margin-bottom: 8px; }
.status-dot  { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
.status-text { font-size: 0.78rem; letter-spacing: 0.08em; text-transform: uppercase; }
.unit-coords { color: #2a4a6a; font-size: 0.72rem; margin-top: 4px; }
.dispatch-order {
    background: #1a1208; border-top: 1px solid #3a2808;
    margin-top: 10px; padding-top: 8px; font-size: 0.78rem;
    color: #c0a060; line-height: 1.6;
}
.dispatch-label { color: #6a5030; font-size: 0.68rem; letter-spacing: 0.1em; text-transform: uppercase; }

.summary-banner {
    background: #10180c; border: 1px solid #2ecc71; border-radius: 8px;
    padding: 14px 18px; color: #2ecc71; font-family: 'Share Tech Mono', monospace;
    font-size: 0.9rem; margin: 10px 0; letter-spacing: 0.03em;
}
.no-dispatch-banner {
    background: #0c1018; border: 1px dashed #1e3a5a; border-radius: 8px;
    padding: 20px; color: #1e3a5a; font-family: 'Share Tech Mono', monospace;
    font-size: 0.82rem; text-align: center; margin: 10px 0;
}
.stat-mini {
    background: #0c1420; border: 1px solid #1a2a3a; border-radius: 6px;
    padding: 10px 14px; text-align: center; margin: 4px 0;
}
.stat-mini-num   { font-size: 1.6rem; font-family: 'Share Tech Mono', monospace; font-weight: 700; }
.stat-mini-label { font-size: 0.68rem; color: #405060; letter-spacing: 0.1em; text-transform: uppercase; }

.incident-card {
    background: #100c08; border: 1px solid #3a2808; border-radius: 8px;
    padding: 14px 18px; margin: 8px 0;
    font-family: 'Share Tech Mono', monospace; font-size: 0.82rem; line-height: 1.8;
}
.incident-title { font-size: 0.78rem; color: #6a5030; letter-spacing: 0.1em;
                  text-transform: uppercase; margin-bottom: 6px; }
</style>
""", unsafe_allow_html=True)

# ── Responder registry (must match comm_agent.py) ──────────────────────────────
ALL_UNITS = [
    {"name": "Fire Stn Alpha",    "type": "fire",         "lat": 13.06, "lng": 80.24, "area": "Adyar"},
    {"name": "Fire Stn Bravo",    "type": "fire",         "lat": 13.10, "lng": 80.29, "area": "Velachery"},
    {"name": "Fire Stn Delta",    "type": "fire",         "lat": 13.04, "lng": 80.31, "area": "Sholinganallur"},
    {"name": "Police Post-1",     "type": "police",       "lat": 13.09, "lng": 80.26, "area": "Anna Nagar"},
    {"name": "Police Post-2",     "type": "police",       "lat": 13.07, "lng": 80.22, "area": "Kodambakkam"},
    {"name": "Police Post-3",     "type": "police",       "lat": 13.12, "lng": 80.28, "area": "Perambur"},
    {"name": "City Hospital",     "type": "hospital",     "lat": 13.08, "lng": 80.30, "area": "Mylapore"},
    {"name": "Metro Med Ctr",     "type": "hospital",     "lat": 13.05, "lng": 80.25, "area": "Guindy"},
    {"name": "Apollo Clinic",     "type": "hospital",     "lat": 13.11, "lng": 80.23, "area": "Kilpauk"},
    {"name": "Ambulance Unit-1",  "type": "ambulance",    "lat": 13.07, "lng": 80.27, "area": "T.Nagar"},
    {"name": "Ambulance Unit-2",  "type": "ambulance",    "lat": 13.09, "lng": 80.24, "area": "Nungambakkam"},
    {"name": "Ambulance Unit-3",  "type": "ambulance",    "lat": 13.05, "lng": 80.26, "area": "Guindy"},
    {"name": "Rescue Team Alpha", "type": "rescue",       "lat": 13.06, "lng": 80.28, "area": "Thiruvanmiyur"},
    {"name": "Rescue Team Bravo", "type": "rescue",       "lat": 13.11, "lng": 80.26, "area": "Kolathur"},
    {"name": "HazMat Unit-1",     "type": "hazmat",       "lat": 13.08, "lng": 80.22, "area": "Vadapalani"},
    {"name": "HazMat Unit-2",     "type": "hazmat",       "lat": 13.06, "lng": 80.30, "area": "Adyar"},
    {"name": "Water Rescue-1",    "type": "water_rescue", "lat": 13.05, "lng": 80.29, "area": "Besant Nagar"},
    {"name": "Water Rescue-2",    "type": "water_rescue", "lat": 13.10, "lng": 80.30, "area": "Tondiarpet"},
]

SERVICE_META = {
    "fire":         {"label": "Fire Department",   "emoji": "🔥", "color": "#e67e22", "bg": "#1a0e00", "border": "#e67e22"},
    "police":       {"label": "Police",            "emoji": "🚔", "color": "#3498db", "bg": "#001428", "border": "#3498db"},
    "hospital":     {"label": "Hospital",          "emoji": "🏥", "color": "#2ecc71", "bg": "#00180e", "border": "#2ecc71"},
    "ambulance":    {"label": "Ambulance",         "emoji": "🚑", "color": "#1abc9c", "bg": "#001814", "border": "#1abc9c"},
    "rescue":       {"label": "Rescue",            "emoji": "🔭", "color": "#9b59b6", "bg": "#130a1a", "border": "#9b59b6"},
    "hazmat":       {"label": "HazMat",            "emoji": "☣️", "color": "#e74c3c", "bg": "#1a0000", "border": "#e74c3c"},
    "water_rescue": {"label": "Water Rescue",      "emoji": "🌊", "color": "#5dade2", "bg": "#001828", "border": "#5dade2"},
}

# ── Build dispatch lookup from session state ────────────────────────────────────
dispatch_result   = st.session_state.get("dispatch_result")
dispatch_incident = st.session_state.get("dispatch_incident")

dispatched_names: dict[str, dict] = {}
if dispatch_result:
    for unit in (dispatch_result.get("selected") or []):
        dispatched_names[unit["name"]] = unit


def render_unit_card(unit: dict):
    """Render a single unit card; highlight if dispatched."""
    meta     = SERVICE_META.get(unit["type"], {})
    color    = meta.get("color", "#888")
    bg       = meta.get("bg", "#0c1420")
    border   = meta.get("border", "#1a2a3a")
    emoji    = meta.get("emoji", "📡")
    label    = meta.get("label", unit["type"])

    is_dispatched = unit["name"] in dispatched_names
    card_class    = "dispatched" if is_dispatched else "available"
    status_color  = "#f0a500" if is_dispatched else "#2ecc71"
    status_txt    = "EN-ROUTE" if is_dispatched else "AVAILABLE"
    status_dot_bg = status_color

    dispatch_html = ""
    if is_dispatched:
        d = dispatched_names[unit["name"]]
        dispatch_html = f"""
        <div class="dispatch-order">
            <div class="dispatch-label">Active dispatch order</div>
            <b>Distance:</b> {d.get('distance_km', '?')} km &nbsp;·&nbsp;
            <b>Reason:</b> {d.get('reason', '')}<br>
            <b>Order:</b> {d.get('message', '')}
        </div>
        """

    st.markdown(f"""
    <div class="unit-card {card_class}" style="background:{bg};border-color:{border}">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div>
                <div class="unit-name">{emoji} {unit['name']}</div>
                <span class="unit-type" style="background:{bg};border:1px solid {color};color:{color}">{label}</span>
            </div>
            <div style="text-align:right">
                <span class="status-dot" style="background:{status_dot_bg}"></span>
                <span class="status-text" style="color:{status_dot_bg}">{status_txt}</span>
            </div>
        </div>
        <div class="unit-coords">{unit['area']} &nbsp;·&nbsp; {unit['lat']}°N {unit['lng']}°E</div>
        {dispatch_html}
    </div>
    """, unsafe_allow_html=True)


def render_service_tab(stype: str, units: list):
    meta = SERVICE_META.get(stype, {})
    color = meta.get("color", "#888")
    dispatched_of_type = [u for u in units if u["name"] in dispatched_names]
    available_of_type  = [u for u in units if u["name"] not in dispatched_names]

    c1, c2, c3 = st.columns(3)
    c1.markdown(
        f'<div class="stat-mini"><div class="stat-mini-num" style="color:{color}">{len(units)}</div>'
        f'<div class="stat-mini-label">Total Units</div></div>', unsafe_allow_html=True)
    c2.markdown(
        f'<div class="stat-mini"><div class="stat-mini-num" style="color:#f0a500">{len(dispatched_of_type)}</div>'
        f'<div class="stat-mini-label">Dispatched</div></div>', unsafe_allow_html=True)
    c3.markdown(
        f'<div class="stat-mini"><div class="stat-mini-num" style="color:#2ecc71">{len(available_of_type)}</div>'
        f'<div class="stat-mini-label">Available</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if dispatched_of_type:
        st.markdown(f"**Dispatched Units**")
        cols = st.columns(min(len(dispatched_of_type), 3))
        for i, unit in enumerate(dispatched_of_type):
            with cols[i % 3]:
                render_unit_card(unit)
        st.markdown("---")

    st.markdown(f"**Available Units**")
    if available_of_type:
        cols = st.columns(min(len(available_of_type), 3))
        for i, unit in enumerate(available_of_type):
            with cols[i % 3]:
                render_unit_card(unit)
    else:
        st.markdown(
            '<div class="no-dispatch-banner">All units of this type are currently deployed.</div>',
            unsafe_allow_html=True,
        )


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🖥️ Services Dashboard")
    st.markdown("---")
    total_dispatched = len(dispatched_names)
    total_available  = len(ALL_UNITS) - total_dispatched

    for label, val, color in [
        ("Total units",  len(ALL_UNITS),    "#5dade2"),
        ("Dispatched",   total_dispatched,  "#f0a500"),
        ("Available",    total_available,   "#2ecc71"),
        ("Service types", len(SERVICE_META), "#9b59b6"),
    ]:
        st.markdown(
            f'<div style="display:flex;gap:8px;padding:2px 0;font-size:0.82rem;font-family:monospace">'
            f'<span style="color:#2a4a6a;min-width:110px">{label}</span>'
            f'<span style="color:{color};font-weight:700">{val}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    if dispatch_result:
        st.markdown("### Active Incident")
        itype = ""
        sev   = ""
        if dispatch_incident:
            itype = (dispatch_incident.get("incident_type") or dispatch_incident.get("type") or "").upper()
            sev   = (dispatch_incident.get("severity") or "").upper()
        sev_colors = {"CRITICAL": "#ff4040", "HIGH": "#ff8c00", "MEDIUM": "#ffd700", "LOW": "#7cfc00"}
        sev_color  = sev_colors.get(sev, "#aaa")
        st.markdown(
            f'<div style="font-family:monospace;font-size:0.8rem;padding:4px 0">'
            f'<span style="color:#5dade2">{itype}</span> · '
            f'<span style="color:{sev_color}">{sev}</span></div>',
            unsafe_allow_html=True,
        )
        st.caption(dispatch_result.get("summary", ""))
    else:
        st.caption("No active dispatch. Run the Comms Agent to dispatch units.")

    st.markdown("---")
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

# ── Main ───────────────────────────────────────────────────────────────────────
st.markdown("# 🖥️ Emergency Services Command Dashboard")
st.markdown(
    "<p style='color:#2a4a6a;font-family:monospace;margin-top:-12px'>"
    "Live unit status · 18 units · 7 service types · Chennai, Tamil Nadu"
    "</p>",
    unsafe_allow_html=True,
)

# Active dispatch banner
if dispatch_result:
    summary = dispatch_result.get("summary", "")
    n_dispatched = len(dispatched_names)
    st.markdown(
        f'<div class="summary-banner">'
        f'🚨 ACTIVE DISPATCH — {n_dispatched} units en-route &nbsp;|&nbsp; {summary}'
        f'</div>',
        unsafe_allow_html=True,
    )

    if dispatch_incident:
        inc = dispatch_incident
        itype  = (inc.get("incident_type") or inc.get("type") or "").upper()
        sev    = (inc.get("severity") or "").upper()
        loc    = inc.get("location") or {}
        area   = loc.get("address") or loc.get("city") or loc.get("name") or "Unknown"
        svc    = inc.get("required_services") or (inc.get("comms_payload") or {}).get("required_services") or []

        st.markdown(
            f'<div class="incident-card">'
            f'<div class="incident-title">Active Incident Details</div>'
            f'<b>Type:</b> {itype} &nbsp;·&nbsp; <b>Severity:</b> {sev} &nbsp;·&nbsp; '
            f'<b>Location:</b> {area}<br>'
            f'<b>Required services:</b> {", ".join(svc) if svc else "—"} &nbsp;·&nbsp; '
            f'<b>Units dispatched:</b> {", ".join(dispatched_names.keys())}'
            f'</div>',
            unsafe_allow_html=True,
        )
else:
    st.markdown(
        '<div class="no-dispatch-banner">'
        'No active dispatch. Complete a dispatch in the Comms Agent to see unit assignments here.'
        '</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── Service tabs ────────────────────────────────────────────────────────────────
tab_labels = ["All Units"] + [
    f"{SERVICE_META[t]['emoji']} {SERVICE_META[t]['label']}"
    for t in SERVICE_META
]
tabs = st.tabs(tab_labels)

# All Units tab
with tabs[0]:
    total_disp = len(dispatched_names)
    total_avail = len(ALL_UNITS) - total_disp
    ca, cb, cc, cd = st.columns(4)
    ca.markdown(
        f'<div class="stat-mini"><div class="stat-mini-num" style="color:#5dade2">{len(ALL_UNITS)}</div>'
        f'<div class="stat-mini-label">Total Units</div></div>', unsafe_allow_html=True)
    cb.markdown(
        f'<div class="stat-mini"><div class="stat-mini-num" style="color:#f0a500">{total_disp}</div>'
        f'<div class="stat-mini-label">Dispatched</div></div>', unsafe_allow_html=True)
    cc.markdown(
        f'<div class="stat-mini"><div class="stat-mini-num" style="color:#2ecc71">{total_avail}</div>'
        f'<div class="stat-mini-label">Available</div></div>', unsafe_allow_html=True)
    cd.markdown(
        f'<div class="stat-mini"><div class="stat-mini-num" style="color:#9b59b6">{len(SERVICE_META)}</div>'
        f'<div class="stat-mini-label">Service Types</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Group by type for all-units view
    for stype, meta in SERVICE_META.items():
        units_of_type = [u for u in ALL_UNITS if u["type"] == stype]
        disp_count = sum(1 for u in units_of_type if u["name"] in dispatched_names)
        color = meta["color"]
        emoji = meta["emoji"]
        label = meta["label"]

        st.markdown(
            f'<div style="font-family:\'Share Tech Mono\',monospace;font-size:0.82rem;'
            f'color:{color};letter-spacing:0.08em;margin:16px 0 4px 0">'
            f'{emoji} {label.upper()} '
            f'<span style="color:#2a4a6a;font-size:0.72rem">· {len(units_of_type)} units'
            f'{" · " + str(disp_count) + " dispatched" if disp_count else ""}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        cols = st.columns(min(len(units_of_type), 3))
        for i, unit in enumerate(units_of_type):
            with cols[i % 3]:
                render_unit_card(unit)

# Per-service tabs
for tab_idx, (stype, meta) in enumerate(SERVICE_META.items(), start=1):
    with tabs[tab_idx]:
        units_of_type = [u for u in ALL_UNITS if u["type"] == stype]
        st.markdown(
            f'<h3>{meta["emoji"]} {meta["label"]}</h3>',
            unsafe_allow_html=True,
        )
        render_service_tab(stype, units_of_type)
