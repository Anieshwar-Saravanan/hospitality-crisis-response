"""
Summary Agent — Incident Pipeline Summary
------------------------------------------
Aggregates outputs from all pipeline agents (Intake, Triage, Comms)
and uses Gemini to produce a concise human-readable incident summary.
"""

import streamlit as st
import json
import os
import re
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Summary Agent", page_icon="📋", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Barlow', sans-serif; }
.stApp { background: #08100d; color: #d8ede2; }
section[data-testid="stSidebar"] { background: #0a1510 !important; border-right: 1px solid #1a3a28; }
h1, h2, h3 { font-family: 'Share Tech Mono', monospace !important; color: #2ecc71 !important; letter-spacing: 0.06em; }

.pipeline-step {
    background: #0c1a12; border: 1px solid #1e3a28;
    border-radius: 8px; padding: 14px 18px; margin: 8px 0;
}
.pipeline-step-title {
    font-family: 'Share Tech Mono', monospace; font-size: 0.78rem;
    letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 8px;
}
.pipeline-arrow {
    text-align: center; color: #1e4a30; font-size: 1.4rem;
    font-family: 'Share Tech Mono', monospace; margin: 2px 0;
}
.field-row {
    display: flex; align-items: flex-start; gap: 8px;
    padding: 3px 0; font-size: 0.82rem;
    font-family: 'Share Tech Mono', monospace;
}
.field-label { color: #3a7a50; min-width: 140px; }
.field-val   { color: #a0d8b8; word-break: break-word; }
.field-null  { color: #1e3a28; font-style: italic; }

.summary-box {
    background: #0a1a0f; border: 1px solid #2ecc71; border-radius: 8px;
    padding: 20px 24px; margin: 10px 0; line-height: 1.8;
    font-size: 0.96rem; color: #c0e8d0;
}
.summary-label {
    font-family: 'Share Tech Mono', monospace; font-size: 0.72rem;
    color: #2ecc71; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 10px;
}
.highlight-card {
    background: #0c1a12; border-left: 3px solid #2ecc71;
    padding: 10px 14px; border-radius: 2px 8px 8px 2px;
    margin: 6px 0; font-size: 0.9rem; color: #a0d8b8; line-height: 1.6;
}
.alert-card {
    background: #180808; border-left: 3px solid #ff4040;
    padding: 10px 14px; border-radius: 2px 8px 8px 2px;
    margin: 6px 0; font-size: 0.9rem; color: #ffaaaa; line-height: 1.6;
}
.info-card {
    background: #080c18; border-left: 3px solid #4080ff;
    padding: 10px 14px; border-radius: 2px 8px 8px 2px;
    margin: 6px 0; font-size: 0.9rem; color: #a0b8f0; line-height: 1.6;
}
.status-banner {
    background: linear-gradient(135deg, #0a1a0f, #051008);
    border: 1px solid #2ecc71; border-radius: 8px;
    padding: 14px 18px; color: #2ecc71;
    font-family: 'Share Tech Mono', monospace; font-size: 1rem;
    margin: 10px 0; text-align: center; letter-spacing: 0.05em;
}
.tag { display: inline-block; padding: 1px 8px; border-radius: 3px;
       font-family: 'Share Tech Mono', monospace; font-size: 0.72rem; margin-right: 4px; }
.tag-critical { background: #2a0000; border: 1px solid #ff4040; color: #ff6060; }
.tag-high     { background: #1a1000; border: 1px solid #ff8c00; color: #ffaa40; }
.tag-medium   { background: #1a1600; border: 1px solid #ffd700; color: #ffd700; }
.tag-low      { background: #081a08; border: 1px solid #7cfc00; color: #7cfc00; }
.tag-green    { background: #081a0f; border: 1px solid #2ecc71; color: #2ecc71; }
.tag-amber    { background: #1a1400; border: 1px solid #f0a500; color: #f0a500; }
.tag-red      { background: #1a0000; border: 1px solid #e74c3c; color: #e74c3c; }

.stTextArea textarea {
    background: #0a1510 !important; color: #d8ede2 !important;
    border: 1px solid #1a3a28 !important; border-radius: 6px;
    font-family: 'Share Tech Mono', monospace !important; font-size: 0.82rem !important;
}
.stButton > button {
    background: #1a6a38 !important; color: white !important;
    border: none !important; border-radius: 6px !important;
    font-family: 'Barlow', sans-serif !important; font-weight: 700 !important;
}
.stButton > button:hover { background: #0f4a28 !important; }
</style>
""", unsafe_allow_html=True)

# ── System Prompt ──────────────────────────────────────────────────────────────
SUMMARY_SYSTEM_PROMPT = """You are the Summary Agent in a multi-agent disaster response system.
You receive outputs from all pipeline agents — Intake, Triage, and Communications — and produce
a clear, structured end-to-end incident summary for command staff and record-keeping.

Your output MUST be raw JSON only. No markdown. No extra text.

{
  "summary_id": "<UUID>",
  "generated_at": "<ISO 8601 UTC>",
  "incident_id": "<from triage or intake>",
  "incident_snapshot": {
    "type": "<incident_type>",
    "severity": "<severity>",
    "location": "<city / address>",
    "reported_at": "<ISO timestamp>",
    "reporter": "<name and phone, or anonymous>"
  },
  "pipeline_summary": {
    "intake": "<1-2 sentences: what the Intake Agent collected and any gaps>",
    "triage": "<1-2 sentences: triage classification, priority, escalation decision>",
    "communications": "<1-2 sentences: which units were dispatched and why>",
    "overall": "<2-3 sentence plain-language summary of the full incident and response for command staff>"
  },
  "key_actions": [
    "<action 1 taken by any agent>",
    "<action 2>",
    "<action 3>"
  ],
  "alerts": [
    "<any critical alerts or warnings the command staff must be aware of>"
  ],
  "status": "active | resolved | escalated",
  "next_steps": [
    "<recommended next step 1>",
    "<recommended next step 2>"
  ]
}
"""

# ── Helpers ────────────────────────────────────────────────────────────────────
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
    raise ValueError(f"Could not parse JSON from Gemini.\n\nRaw:\n{text[:2000]}")


def call_summary_gemini(api_key: str, combined: dict) -> dict:
    client = genai.Client(api_key=api_key)
    prompt = (
        f"Pipeline agent outputs:\n{json.dumps(combined, indent=2)}\n\n"
        "Generate the incident pipeline summary JSON."
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SUMMARY_SYSTEM_PROMPT,
            temperature=0.1,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return extract_json(response.text)


def frow(label: str, value) -> str:
    has = value is not None and value != "" and value != []
    dot = '<span style="color:#2ecc71">●</span>' if has else '<span style="color:#1e3a28">○</span>'
    if has:
        display = ", ".join(str(v) for v in value) if isinstance(value, list) else str(value)
        val_html = f'<span class="field-val">{display}</span>'
    else:
        val_html = '<span class="field-null">—</span>'
    return (
        f'<div class="field-row">{dot}&nbsp;'
        f'<span class="field-label">{label}</span>{val_html}</div>'
    )


def _safe_parse(raw: str) -> dict | None:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


# ── Session State ──────────────────────────────────────────────────────────────
if "summary_result" not in st.session_state:
    st.session_state.summary_result = None

# ── Pre-populate from shared session state ─────────────────────────────────────
_default_intake  = st.session_state.get("shared_incident_json", "")
_default_triage  = st.session_state.get("shared_triage_json", "")

SAMPLE_COMBINED = json.dumps({
    "intake": {
        "status": "complete",
        "incident_id": "0556ec85-afca-4c2f-9403-868ac29eb59c",
        "reported_at": "2026-04-23T13:21:34Z",
        "incident_type": "fire",
        "severity": "critical",
        "description": "Fire on 4th floor of ABC apartments, 5 people trapped",
        "location": {"address": "4th floor, ABC apartments", "city": "Chennai"},
        "reporter": {"name": "Anish", "phone": "7417450999", "is_anonymous": False},
        "casualties": {"injured": 0, "dead": 0, "trapped": 5},
        "hazards": ["fire"],
        "required_services": ["fire brigade", "rescue", "ambulance"],
    },
    "triage": {
        "triage_id": "t-001",
        "triaged_at": "2026-04-23T13:22:10Z",
        "incident_type": "fire",
        "severity": "critical",
        "priority_score": 1,
        "escalation_level": "critical",
        "sop_references": ["SOP-FIRE-001", "SOP-RESCUE-003"],
        "action_plan": [
            "Evacuate all floors above and below the fire floor immediately.",
            "Deploy fire suppression teams to 4th floor with hose lines.",
            "Coordinate rescue team entry for trapped persons.",
            "Stage ambulances at building entrance.",
        ],
        "routing": {
            "response_agent": True,
            "coordination_agent": True,
            "comms_agent": True,
            "escalate_to_command": True,
        },
        "comms_payload": {
            "alert_level": "red",
            "broadcast_message": "Critical fire at ABC Apartments 4th floor, Chennai. 5 trapped. Fire, rescue, and ambulance units dispatched. Command escalation active.",
            "affected_area": "Chennai",
            "required_services": ["fire brigade", "rescue", "ambulance"],
        },
    },
    "communications": {
        "summary": "Critical residential fire with 5 trapped persons. Nearest fire, police, and hospital units selected.",
        "selected": [
            {"name": "Fire Stn Alpha", "type": "fire",     "distance_km": 2.1, "message": "Respond immediately to 4th floor fire at ABC Apartments."},
            {"name": "Police Post-1",  "type": "police",   "distance_km": 1.8, "message": "Provide perimeter control and crowd management at ABC Apartments."},
            {"name": "City Hospital",  "type": "hospital", "distance_km": 2.4, "message": "Prepare for up to 5 trauma patients from residential fire."},
        ],
    },
}, indent=2)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 Summary Agent")
    st.markdown("---")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        st.success("Gemini API key loaded from .env")
    else:
        st.warning("Set GEMINI_API_KEY in .env to generate summary.")

    st.markdown("---")
    r = st.session_state.summary_result
    if r:
        st.markdown("### 📋 Summary")
        snap = r.get("incident_snapshot", {})
        for label, val in [
            ("incident_id", (r.get("incident_id") or "")[:12] + "…"),
            ("type",        snap.get("type")),
            ("severity",    snap.get("severity")),
            ("location",    snap.get("location")),
            ("status",      r.get("status")),
            ("next steps",  str(len(r.get("next_steps", [])))),
        ]:
            st.markdown(frow(label, val), unsafe_allow_html=True)
    else:
        st.caption("No summary yet.")

    st.markdown("---")
    if st.button("🔄 Clear", use_container_width=True):
        st.session_state.summary_result = None
        st.rerun()

# ── Main ───────────────────────────────────────────────────────────────────────
st.markdown("# 📋 Summary Agent")
st.markdown(
    "Aggregates outputs from all pipeline agents and produces a concise incident summary for command staff."
)
st.markdown("---")

left, right = st.columns([2, 3], gap="large")

# ── LEFT: Inputs ───────────────────────────────────────────────────────────────
with left:
    st.markdown("### 📥 Pipeline Input")

    tab_auto, tab_manual = st.tabs(["Auto (from session)", "Manual JSON"])

    with tab_auto:
        intake_parsed  = _safe_parse(_default_intake)
        triage_parsed  = _safe_parse(_default_triage)
        has_intake  = intake_parsed  is not None
        has_triage  = triage_parsed  is not None

        st.markdown(
            frow("Intake data",  "loaded from session" if has_intake  else None) +
            frow("Triage data",  "loaded from session" if has_triage  else None),
            unsafe_allow_html=True,
        )
        if not has_intake or not has_triage:
            st.info(
                "Complete the Intake and Triage steps first, or use **Manual JSON** tab "
                "to paste data directly."
            )

        combined_auto = {}
        if has_intake:
            combined_auto["intake"] = intake_parsed
        if has_triage:
            combined_auto["triage"] = triage_parsed

        run_auto = st.button(
            "📋 Generate Summary (session data)",
            disabled=(not api_key or not combined_auto),
            use_container_width=True,
            key="run_auto",
        )

    with tab_manual:
        manual_json = st.text_area(
            "Paste combined pipeline JSON",
            value=SAMPLE_COMBINED,
            height=380,
            label_visibility="collapsed",
        )
        run_manual = st.button(
            "📋 Generate Summary (manual)",
            disabled=not api_key,
            use_container_width=True,
            key="run_manual",
        )

    # ── Trigger summary ──────────────────────────────────────────────────────
    if (run_auto or run_manual) and api_key:
        if not GENAI_AVAILABLE:
            st.error("Missing dependency. Run:  pip install google-genai")
            st.stop()

        if run_auto:
            combined_data = combined_auto
        else:
            try:
                combined_data = json.loads(manual_json)
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")
                st.stop()

        with st.spinner("📋 Gemini is generating the incident summary…"):
            try:
                result = call_summary_gemini(api_key.strip(), combined_data)
            except Exception as e:
                st.error(f"Gemini API error: {e}")
                st.stop()

        if not result.get("generated_at"):
            result["generated_at"] = datetime.now(timezone.utc).isoformat()

        st.session_state.summary_result = result
        st.rerun()

    if st.session_state.summary_result:
        st.download_button(
            "⬇️ Download Summary JSON",
            data=json.dumps(st.session_state.summary_result, indent=2),
            file_name="incident_summary.json",
            mime="application/json",
        )

# ── RIGHT: Output ──────────────────────────────────────────────────────────────
with right:
    st.markdown("### 📤 Summary Output")
    result = st.session_state.summary_result

    if result is None:
        st.markdown("""
        <div style="color:#1a3a28;font-family:'Share Tech Mono',monospace;
             padding:60px 20px;border:1px dashed #1a3a28;border-radius:8px;
             text-align:center;font-size:0.82rem;line-height:2.2">
        { }<br><span style="font-size:0.72rem">Awaiting summary generation…</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        snap   = result.get("incident_snapshot", {})
        status = result.get("status", "active")
        sev    = snap.get("severity", "")

        status_colors = {"active": "#f0a500", "resolved": "#2ecc71", "escalated": "#ff4040"}
        status_color  = status_colors.get(status, "#aaa")

        st.markdown(
            f'<div class="status-banner">'
            f'📋 SUMMARY GENERATED &nbsp;|&nbsp; '
            f'{snap.get("type","").upper()} — {sev.upper()} &nbsp;|&nbsp; '
            f'<span style="color:{status_color}">{status.upper()}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        tab_overview, tab_pipeline, tab_actions, tab_raw = st.tabs(
            ["🗂 Overview", "🔗 Pipeline", "✅ Actions & Next Steps", "🗂 Raw JSON"]
        )

        # ── Overview ──────────────────────────────────────────────────────────
        with tab_overview:
            ps = result.get("pipeline_summary", {})
            overall_text = ps.get("overall", "")
            if overall_text:
                st.markdown(
                    f'<div class="summary-box">'
                    f'<div class="summary-label">Incident Summary</div>'
                    f'{overall_text}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            c1, c2 = st.columns(2)
            with c1:
                sev_tag = f'<span class="tag tag-{sev}">{sev.upper()}</span>' if sev else ""
                st.markdown(f"""
                <div class="pipeline-step">
                <div class="pipeline-step-title" style="color:#2ecc71">Incident Snapshot</div>
                {frow("type",       snap.get("type"))}
                {frow("severity",   sev_tag if sev else None)}
                {frow("location",   snap.get("location"))}
                {frow("reported",   snap.get("reported_at"))}
                {frow("reporter",   snap.get("reporter"))}
                </div>
                """, unsafe_allow_html=True)
            with c2:
                alerts = result.get("alerts", [])
                if alerts:
                    alert_html = "".join(
                        f'<div class="alert-card">⚠ {a}</div>' for a in alerts
                    )
                    st.markdown(
                        f'<div class="pipeline-step">'
                        f'<div class="pipeline-step-title" style="color:#ff6060">Alerts for Command</div>'
                        f'{alert_html}</div>',
                        unsafe_allow_html=True,
                    )

        # ── Pipeline ──────────────────────────────────────────────────────────
        with tab_pipeline:
            ps = result.get("pipeline_summary", {})
            steps = [
                ("🚨 Intake Agent",         ps.get("intake"),         "#ff4040"),
                ("🧠 Triage Agent",         ps.get("triage"),         "#f0a500"),
                ("📡 Communications Agent", ps.get("communications"), "#3498db"),
            ]
            for title, text, color in steps:
                if text:
                    st.markdown(
                        f'<div class="pipeline-step">'
                        f'<div class="pipeline-step-title" style="color:{color}">{title}</div>'
                        f'<span style="color:#a0d8b8;font-size:0.9rem;line-height:1.7">{text}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown('<div class="pipeline-arrow">↓</div>', unsafe_allow_html=True)

            st.markdown(
                f'<div class="pipeline-step" style="border-color:#2ecc71">'
                f'<div class="pipeline-step-title" style="color:#2ecc71">📋 Summary Agent</div>'
                f'<span style="color:#a0d8b8;font-size:0.9rem">Aggregated all pipeline outputs into this report.</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # ── Actions & Next Steps ───────────────────────────────────────────────
        with tab_actions:
            key_actions = result.get("key_actions", [])
            next_steps  = result.get("next_steps", [])

            if key_actions:
                st.markdown("**Key Actions Taken:**")
                for action in key_actions:
                    st.markdown(
                        f'<div class="highlight-card">✔ {action}</div>',
                        unsafe_allow_html=True,
                    )

            if next_steps:
                st.markdown("**Recommended Next Steps:**")
                for step in next_steps:
                    st.markdown(
                        f'<div class="info-card">→ {step}</div>',
                        unsafe_allow_html=True,
                    )

        # ── Raw JSON ──────────────────────────────────────────────────────────
        with tab_raw:
            st.code(json.dumps(result, indent=2), language="json")
