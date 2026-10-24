"""
Multimodal Construction Intelligence Platform
Skill Wallet Capstone Project 1

Single-file Streamlit app. No database. Deploys on Streamlit Community Cloud.
Run locally:  streamlit run app.py
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from datetime import datetime

import streamlit as st

try:
    from google import genai
    from google.genai import types

    GENAI_AVAILABLE = True
except Exception:  # SDK missing -> demo mode only
    GENAI_AVAILABLE = False

# ----------------------------------------------------------------------------
# Page config & styling
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Construction Intelligence Platform",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
:root { --brand:#f59e0b; --ink:#0f172a; --card:#ffffff; --muted:#64748b; }
.block-container { padding-top: 1.6rem; }
.hero {
    background: linear-gradient(120deg,#0f172a 0%,#1e3a5f 60%,#f59e0b 160%);
    color:#fff; padding:1.4rem 1.8rem; border-radius:16px; margin-bottom:1rem;
}
.hero h1 { margin:0; font-size:1.8rem; color:#fff; }
.hero p { margin:.3rem 0 0 0; opacity:.85; }
.mcard {
    background:var(--card); border:1px solid #e2e8f0; border-left:5px solid var(--brand);
    border-radius:12px; padding:.9rem 1.1rem; box-shadow:0 1px 3px rgba(0,0,0,.06);
}
.mcard .lbl { color:var(--muted); font-size:.78rem; text-transform:uppercase; letter-spacing:.05em; }
.mcard .val { color:var(--ink); font-size:1.65rem; font-weight:700; line-height:1.2; }
.mcard .sub { color:var(--muted); font-size:.8rem; }
.pill {
    display:inline-block; padding:.18rem .7rem; border-radius:999px;
    font-size:.78rem; font-weight:600; color:#fff;
}
.p-ok{background:#16a34a}.p-low{background:#0ea5e9}.p-med{background:#f59e0b}
.p-high{background:#ea580c}.p-crit{background:#dc2626}.p-na{background:#64748b}
.hazard {
    border:1px solid #e2e8f0; border-radius:10px; padding:.7rem 1rem;
    margin-bottom:.5rem; background:#f8fafc; color:#0f172a;
}
.alert-box { border-radius:12px; padding:.8rem 1.1rem; margin-bottom:.6rem; color:#0f172a; }
.alert-red{background:#fee2e2;border-left:5px solid #dc2626}
.alert-amber{background:#fef3c7;border-left:5px solid #f59e0b}
.alert-blue{background:#dbeafe;border-left:5px solid #2563eb}
.alert-green{background:#dcfce7;border-left:5px solid #16a34a}
@media (prefers-color-scheme: dark) {
    .mcard{background:#1e293b;border-color:#334155}
    .mcard .val{color:#f1f5f9}
    .hazard{background:#1e293b;border-color:#334155;color:#f1f5f9}
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Constants & prompts
# ----------------------------------------------------------------------------
SEVERITY_CLASS = {"Low": "p-low", "Medium": "p-med", "High": "p-high", "Critical": "p-crit"}
STATUS_CLASS = {
    "Compliant": "p-ok", "Needs Improvement": "p-med", "Non-Compliant": "p-high",
    "Critical Violation": "p-crit",
}
URGENCY_CLASS = {"Monitor": "p-low", "Planned Repair": "p-med", "Urgent": "p-high", "Immediate": "p-crit"}

SAFETY_PROMPT = """You are a certified construction safety officer auditing a site photograph
against OSHA 29 CFR 1926 and Indian construction practice (IS 456:2000 for concrete work,
IS 3764 for excavation safety, IS 7969 for general site safety).
Assess every visible worker for: helmet, high-visibility vest, steel-toe safety boots,
safety harness (where working at height). Also identify site hazards (scaffolding, edge
protection, housekeeping, exposed rebar, electrical, excavation, etc.).
If something is not visible, mark it "Not Visible" instead of guessing.
Respond with ONLY valid JSON in exactly this schema:
{
 "safety_score": <int 0-100>,
 "overall_status": "Compliant" | "Needs Improvement" | "Non-Compliant" | "Critical Violation",
 "workers_detected": <int>,
 "summary": "<2 sentence summary>",
 "ppe_detection": {
   "helmet": {"status": "Compliant"|"Violation"|"Not Visible", "note": "<short>"},
   "high_vis_vest": {"status": "...", "note": "..."},
   "steel_toe_boots": {"status": "...", "note": "..."},
   "safety_harness": {"status": "...", "note": "..."}
 },
 "hazards": [
   {"hazard": "<name>", "severity": "Low"|"Medium"|"High"|"Critical",
    "standard_reference": "<e.g. OSHA 1926.501>", "remedy": "<corrective action>"}
 ]
}"""

CRACK_PROMPT = """You are a senior structural engineer diagnosing a concrete/masonry surface
photograph following IS 456:2000, IS 13935 (seismic repair) and ACI 224R crack guidelines.
Classify the dominant defect as exactly one of:
"Hairline", "Settlement", "Structural Shear", "Thermal Expansion", "Spalling".
Estimate crack width in mm from visual cues (state uncertainty). Be conservative: if a
photo is unclear, say so in "confidence_note" and recommend an on-site inspection.
Respond with ONLY valid JSON in exactly this schema:
{
 "defect_type": "<one of the five>",
 "estimated_crack_width_mm": <number>,
 "crack_pattern": "<vertical|horizontal|diagonal|stair-step|map|none>",
 "severity": "Low" | "Medium" | "High" | "Critical",
 "urgency": "Monitor" | "Planned Repair" | "Urgent" | "Immediate",
 "root_causes": ["..."],
 "recommended_repairs": [{"method": "<e.g. Epoxy injection>", "details": "<how/where>"}],
 "structural_risk": "<one paragraph>",
 "confidence_note": "<limitations of photo-based diagnosis>"
}"""

CHAT_SYSTEM = """You are SiteMate, an expert civil/construction engineering assistant for Indian
sites. Give practical, concise, step-by-step answers referencing IS codes (IS 456, IS 800,
IS 1893, IS 2502, NBC 2016) and OSHA where relevant. Use metric units and INR. For
safety-critical or structural-adequacy questions, remind the user that a licensed structural
engineer must verify on site. Current site weather context: {weather}."""

WEATHER_ADVISORIES = {
    "High Wind": {
        "icon": "🌬️", "tone": "red",
        "alerts": [
            ("red", "Suspend crane & hoisting operations when sustained wind exceeds ~36 km/h (OSHA 1926.1431 / IS 807)."),
            ("red", "Stop work on scaffolds, formwork stripping and exposed edges; secure loose sheets, rebar bundles and materials."),
            ("amber", "Lower tower-crane jib to weathervane (free-slewing) mode; barricade the fall zone."),
            ("amber", "Brace temporary hoardings and tall formwork; inspect scaffold ties before resuming."),
        ],
    },
    "Heavy Rain": {
        "icon": "🌧️", "tone": "blue",
        "alerts": [
            ("red", "Electrical hazard: de-energise temporary distribution boards in wet areas, use ELCB/RCCB (30 mA), no cable joints on the ground."),
            ("amber", "Concrete curing protocol: halt fresh pours; cover placed concrete with tarpaulin to avoid surface wash-out (IS 456 cl. 13)."),
            ("amber", "Excavations: check shoring and dewater; keep spoil 1 m+ away from the edge (IS 3764)."),
            ("blue", "Protect cement from moisture - stack on pallets, covered; slip-resistant walkways for workers."),
        ],
    },
    "Extreme Heat": {
        "icon": "🔥", "tone": "amber",
        "alerts": [
            ("red", "Heat-stress control: mandatory shade/water breaks (approx. 10 min per hour above 40 °C WBGT-equivalent); watch for heat exhaustion."),
            ("amber", "Concrete curing protocol: pour early morning/evening; use chilled water/ice, retarders; start wet curing within hours (IS 456 cl. 13.5), keep moist at least 7 days."),
            ("amber", "Avoid bare-metal contact (scaffold, rebar) in midday sun; rotate workers on exposed roof/steel work."),
            ("blue", "Provide ORS/electrolytes and a first-aid point; reschedule heavy manual tasks."),
        ],
    },
    "Normal": {
        "icon": "☀️", "tone": "green",
        "alerts": [
            ("green", "Conditions normal: proceed with the planned schedule and the daily toolbox talk."),
            ("blue", "Routine checks: PPE compliance, scaffold tags, housekeeping, and temporary electrical inspection."),
            ("blue", "Standard curing: keep concrete moist for 7 days (OPC) / 10 days (blended cement) per IS 456."),
        ],
    },
}

# Valuation model constants (illustrative planning averages, INR)
COST_PER_SQFT = {  # construction cost, Rs/sqft
    "Residential (RCC Framed)": 1800, "Commercial (RCC Framed)": 2400,
    "Industrial (PEB / Steel)": 1700, "Load-Bearing Masonry": 1400, "Luxury Villa": 3200,
}
STEEL_KG_PER_SQFT = {
    "Residential (RCC Framed)": 4.0, "Commercial (RCC Framed)": 5.0,
    "Industrial (PEB / Steel)": 9.0, "Load-Bearing Masonry": 2.5, "Luxury Villa": 4.5,
}
CEMENT_BAGS_PER_SQFT = {
    "Residential (RCC Framed)": 0.45, "Commercial (RCC Framed)": 0.5,
    "Industrial (PEB / Steel)": 0.3, "Load-Bearing Masonry": 0.5, "Luxury Villa": 0.55,
}
TIER_COST_FACTOR = {"Tier 1": 1.25, "Tier 2": 1.0, "Tier 3": 0.85}
TIER_MARKET_RATE = {"Tier 1": 9500, "Tier 2": 5200, "Tier 3": 3200}  # Rs/sqft built-up market value
MILESTONES = [
    (0, "Site Prep & Excavation"), (10, "Foundation"), (30, "Plinth & Superstructure"),
    (55, "Masonry & Roofing"), (75, "MEP & Plastering"), (90, "Finishing & Fit-out"),
    (100, "Handover"),
]


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def fmt_inr(amount: float) -> str:
    """Format INR in Lakhs / Crores."""
    if amount >= 1e7:
        return f"₹ {amount / 1e7:,.2f} Cr"
    return f"₹ {amount / 1e5:,.2f} Lakh"


def metric_card(label: str, value: str, sub: str = "") -> str:
    return (f'<div class="mcard"><div class="lbl">{label}</div>'
            f'<div class="val">{value}</div><div class="sub">{sub}</div></div>')


def pill(text: str, css: str) -> str:
    return f'<span class="pill {css}">{text}</span>'


def extract_json(text: str) -> dict:
    """Parse JSON from a model response, tolerating code fences / stray prose."""
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def get_client(api_key: str):
    if not (GENAI_AVAILABLE and api_key):
        return None
    return genai.Client(api_key=api_key)


def analyze_image(client, model: str, prompt: str, image_bytes: bytes, mime: str) -> dict:
    resp = client.models.generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime), prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
    )
    return extract_json(resp.text)


def seed_from(data: bytes, mod: int) -> int:
    return int(hashlib.md5(data).hexdigest(), 16) % mod


# ----------------------------------------------------------------------------
# Demo-mode fallbacks (deterministic by image hash)
# ----------------------------------------------------------------------------
def demo_safety(image_bytes: bytes) -> dict:
    s = seed_from(image_bytes, 3)
    score = [58, 74, 41][s]
    status = ["Needs Improvement", "Needs Improvement", "Non-Compliant"][s]
    return {
        "safety_score": score, "overall_status": status, "workers_detected": 3 + s,
        "summary": "DEMO DATA: Most workers wear helmets, but vest and harness compliance is inconsistent. "
                   "Edge protection and housekeeping need attention.",
        "ppe_detection": {
            "helmet": {"status": "Compliant", "note": "Visible on most workers."},
            "high_vis_vest": {"status": "Violation", "note": "One worker without vest."},
            "steel_toe_boots": {"status": "Not Visible", "note": "Footwear not clearly visible."},
            "safety_harness": {"status": "Violation", "note": "Work at height without harness anchorage."},
        },
        "hazards": [
            {"hazard": "Unprotected floor edge", "severity": "Critical",
             "standard_reference": "OSHA 1926.502 / IS 7969",
             "remedy": "Install guardrails (top rail 1.0 m, mid rail, toe board) immediately."},
            {"hazard": "Exposed projecting rebar", "severity": "High",
             "standard_reference": "OSHA 1926.701(b)",
             "remedy": "Fit mushroom caps on all protruding reinforcement."},
            {"hazard": "Material stacked in walkway", "severity": "Medium",
             "standard_reference": "OSHA 1926.25",
             "remedy": "Clear and designate storage zones; maintain 1 m clear access."},
            {"hazard": "Loose temporary wiring", "severity": "Low",
             "standard_reference": "IS 732 / OSHA 1926.405",
             "remedy": "Route cables overhead on insulated supports."},
        ],
    }


def demo_crack(image_bytes: bytes) -> dict:
    s = seed_from(image_bytes, 5)
    types_ = ["Hairline", "Settlement", "Structural Shear", "Thermal Expansion", "Spalling"]
    width = [0.2, 3.5, 5.0, 1.2, 2.0][s]
    sev = ["Low", "High", "Critical", "Medium", "Medium"][s]
    urg = ["Monitor", "Urgent", "Immediate", "Planned Repair", "Planned Repair"][s]
    return {
        "defect_type": types_[s], "estimated_crack_width_mm": width,
        "crack_pattern": ["map", "stair-step", "diagonal", "horizontal", "none"][s],
        "severity": sev, "urgency": urg,
        "root_causes": ["DEMO DATA: Differential foundation movement or soil moisture variation",
                        "Inadequate curing / shrinkage during early age",
                        "Thermal cycling and lack of movement joints"],
        "recommended_repairs": [
            {"method": "Epoxy injection", "details": "Pressure-inject low-viscosity epoxy for cracks 0.2-5 mm after cleaning."},
            {"method": "Structural re-grouting", "details": "Use non-shrink polymer-modified grout for voids/wider cracks."},
            {"method": "Surface polymer-modified repair mortar", "details": "For spalled cover; treat exposed rebar with anti-corrosive primer."},
        ],
        "structural_risk": "Demonstration output only. Real diagnosis requires crack monitoring "
                           "(tell-tales) and a site inspection by a licensed structural engineer.",
        "confidence_note": "Demo mode: no image analysis performed.",
    }


def demo_chat_reply(question: str, weather: str) -> str:
    q = question.lower()
    if "curing" in q or "cure" in q:
        return ("**Curing (IS 456 cl. 13.5):** start moist curing as soon as the concrete is hard enough not to be "
                "marred; keep continuously wet for at least 7 days (OPC) or 10 days (PPC/blended, or in hot/dry "
                "weather). Use wet hessian, ponding, or curing compound.\n\n*(Demo mode - add a Gemini key for full answers.)*")
    if "slump" in q:
        return ("**Slump guide (IS 456 Table 7):** 25-75 mm for lightly reinforced sections, 50-100 mm for "
                "normal RCC beams/slabs, 100-150 mm for heavily reinforced/pumped concrete.\n\n*(Demo mode.)*")
    if "scaffold" in q:
        return ("**Scaffold checks:** base plates on firm ground, tied every 4 m vertically, full guardrails and "
                "toe boards, tagged inspection before each shift.\n\n*(Demo mode.)*")
    return (f"I'm running in **demo mode** (weather context: {weather}). I can answer basic questions on curing, "
            "slump, scaffolding and PPE here. Add a Gemini API key in the sidebar for full engineering assistance.")


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🏗️ Control Panel")
    api_key = st.text_input(
        "Google Gemini API key", type="password",
        value=st.secrets.get("GEMINI_API_KEY", "") if hasattr(st, "secrets") else "",
        help="Stored only in this session. Leave blank for demonstration mode.",
    )
    model_name = st.selectbox("Model", ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"], index=0)
    client = get_client(api_key.strip()) if api_key else None
    DEMO = client is None
    if DEMO:
        st.warning("🧪 **Demo mode** - sample outputs, no AI calls." +
                   ("" if GENAI_AVAILABLE else " (google-genai not installed)"))
    else:
        st.success("✅ Live mode - Gemini connected")

    st.divider()
    st.markdown("### 🧭 Features")
    st.markdown("- 🦺 Site Safety & PPE Audit\n- 🧱 Crack Diagnostics\n- 💰 Planning & Valuation\n- 🌦️ Daily Site Assistant")
    st.divider()
    with st.expander("🏛️ Architecture overview"):
        st.markdown(
            "**UI:** Streamlit tabs + custom CSS  \n"
            "**Vision AI:** Gemini multimodal (image + structured-JSON prompt)  \n"
            "**Valuation:** deterministic rule-based cost model (INR)  \n"
            "**Rendering:** Pollinations AI image URL  \n"
            "**Chat:** Gemini with engineering system prompt, session-state memory  \n"
            "**State/DB:** `st.session_state` only - zero external DB"
        )
    st.caption("AI output is advisory. Safety & structural decisions need a qualified professional.")

# ----------------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------------
st.markdown(
    '<div class="hero"><h1>🏗️ Multimodal Construction Intelligence Platform</h1>'
    "<p>AI-powered safety audits, structural diagnostics, project valuation and a weather-aware site assistant.</p></div>",
    unsafe_allow_html=True,
)

tab1, tab2, tab3, tab4 = st.tabs([
    "🦺 Safety & PPE Audit", "🧱 Crack Diagnostics", "💰 Planning & Valuation", "🌦️ Site Assistant",
])


def read_upload(file):
    data = file.getvalue()
    mime = file.type or ("image/png" if file.name.lower().endswith("png") else "image/jpeg")
    return data, mime


# ----------------------------------------------------------------------------
# Tab 1 - Safety & PPE
# ----------------------------------------------------------------------------
with tab1:
    st.subheader("Site Safety & PPE Compliance Audit")
    st.caption("Standards: OSHA 29 CFR 1926 · IS 456:2000 · IS 7969")
    up = st.file_uploader("Upload a construction site photo", type=["jpg", "jpeg", "png"], key="safety_up")
    if up:
        data, mime = read_upload(up)
        c1, c2 = st.columns([1, 1.3])
        c1.image(data, caption=up.name, use_container_width=True)
        if c2.button("🔍 Run Safety Audit", type="primary", key="safety_btn"):
            with st.spinner("Analyzing site photo..."):
                try:
                    st.session_state.safety = (demo_safety(data) if DEMO else
                                               analyze_image(client, model_name, SAFETY_PROMPT, data, mime))
                except Exception as e:
                    st.error(f"Analysis failed: {e}")
                    st.session_state.pop("safety", None)

    r = st.session_state.get("safety")
    if r:
        try:
            score = int(r.get("safety_score", 0))
            status = r.get("overall_status", "Needs Improvement")
            hazards = r.get("hazards", [])
            m1, m2, m3, m4 = st.columns(4)
            m1.markdown(metric_card("Safety Score", f"{score}/100", "0 = unsafe, 100 = exemplary"), unsafe_allow_html=True)
            m2.markdown(metric_card("Overall Status", pill(status, STATUS_CLASS.get(status, "p-na"))), unsafe_allow_html=True)
            m3.markdown(metric_card("Workers Detected", str(r.get("workers_detected", "-"))), unsafe_allow_html=True)
            crit = sum(1 for h in hazards if h.get("severity") in ("High", "Critical"))
            m4.markdown(metric_card("High/Critical Hazards", str(crit), f"{len(hazards)} total"), unsafe_allow_html=True)
            st.progress(max(0, min(score, 100)) / 100)
            st.info(r.get("summary", ""))

            st.markdown("#### PPE Checklist")
            labels = {"helmet": "⛑️ Helmet", "high_vis_vest": "🦺 High-Vis Vest",
                      "steel_toe_boots": "🥾 Steel-Toe Boots", "safety_harness": "🪢 Safety Harness"}
            cols = st.columns(4)
            for col, (k, lab) in zip(cols, labels.items()):
                item = r.get("ppe_detection", {}).get(k, {})
                s = item.get("status", "Not Visible")
                css = {"Compliant": "p-ok", "Violation": "p-crit"}.get(s, "p-na")
                col.markdown(f'<div class="hazard"><b>{lab}</b><br>{pill(s, css)}<br>'
                             f'<small>{item.get("note", "")}</small></div>', unsafe_allow_html=True)

            st.markdown("#### Identified Hazards")
            order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
            for h in sorted(hazards, key=lambda x: order.get(x.get("severity"), 9)):
                sev = h.get("severity", "Low")
                st.markdown(
                    f'<div class="hazard">{pill(sev, SEVERITY_CLASS.get(sev, "p-na"))} '
                    f'<b>{h.get("hazard", "")}</b> <small>({h.get("standard_reference", "")})</small><br>'
                    f'🛠️ <i>{h.get("remedy", "")}</i></div>', unsafe_allow_html=True)

            report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
                      "mode": "demo" if DEMO else "live", "report": r}
            st.download_button("⬇️ Download JSON report", json.dumps(report, indent=2),
                               file_name="safety_audit_report.json", mime="application/json")
        except Exception as e:
            st.error(f"Could not render report: {e}")
            st.json(r)
    elif not up:
        st.info("Upload a site photo to begin.")

# ----------------------------------------------------------------------------
# Tab 2 - Crack diagnostics
# ----------------------------------------------------------------------------
with tab2:
    st.subheader("Crack Diagnostics & Structural Integrity")
    st.caption("Classifies: Hairline · Settlement · Structural Shear · Thermal Expansion · Spalling")
    up2 = st.file_uploader("Upload concrete / wall surface photo", type=["jpg", "jpeg", "png"], key="crack_up")
    if up2:
        data2, mime2 = read_upload(up2)
        c1, c2 = st.columns([1, 1.3])
        c1.image(data2, caption=up2.name, use_container_width=True)
        if c2.button("🔬 Diagnose Defect", type="primary", key="crack_btn"):
            with st.spinner("Running structural diagnostics..."):
                try:
                    st.session_state.crack = (demo_crack(data2) if DEMO else
                                              analyze_image(client, model_name, CRACK_PROMPT, data2, mime2))
                except Exception as e:
                    st.error(f"Diagnosis failed: {e}")
                    st.session_state.pop("crack", None)

    c = st.session_state.get("crack")
    if c:
        try:
            sev, urg = c.get("severity", "Low"), c.get("urgency", "Monitor")
            m1, m2, m3, m4 = st.columns(4)
            m1.markdown(metric_card("Defect Type", c.get("defect_type", "-"), c.get("crack_pattern", "")), unsafe_allow_html=True)
            m2.markdown(metric_card("Est. Crack Width", f'{c.get("estimated_crack_width_mm", 0)} mm', "visual estimate"), unsafe_allow_html=True)
            m3.markdown(metric_card("Severity", pill(sev, SEVERITY_CLASS.get(sev, "p-na"))), unsafe_allow_html=True)
            m4.markdown(metric_card("Urgency", pill(urg, URGENCY_CLASS.get(urg, "p-na"))), unsafe_allow_html=True)

            st.markdown("#### Probable Root Causes")
            for cause in c.get("root_causes", []):
                st.markdown(f"- {cause}")
            st.markdown("#### Recommended Engineering Repairs")
            for rep in c.get("recommended_repairs", []):
                st.markdown(f'<div class="hazard"><b>🔧 {rep.get("method", "")}</b><br>{rep.get("details", "")}</div>',
                            unsafe_allow_html=True)
            st.warning(f"**Structural risk:** {c.get('structural_risk', '')}")
            st.caption(f"ℹ️ {c.get('confidence_note', '')}")
            st.download_button("⬇️ Download JSON report", json.dumps(c, indent=2),
                               file_name="crack_diagnostic_report.json", mime="application/json")
        except Exception as e:
            st.error(f"Could not render diagnosis: {e}")
            st.json(c)
    elif not up2:
        st.info("Upload a surface photo to begin.")

# ----------------------------------------------------------------------------
# Tab 3 - Planning & valuation
# ----------------------------------------------------------------------------
with tab3:
    st.subheader("Project Planning & Real Estate Valuation")
    st.caption("Indicative planning model using average Indian rates - not a certified valuation.")
    i1, i2, i3 = st.columns(3)
    stype = i1.selectbox("Structure type", list(COST_PER_SQFT))
    sqft = i2.number_input("Built-up area (sq ft)", min_value=100, max_value=1_000_000, value=2000, step=100)
    tier = i3.selectbox("Location tier", list(TIER_COST_FACTOR),
                        help="Tier 1: Mumbai, Delhi NCR, Bengaluru… | Tier 2: Indore, Jaipur, Pune… | Tier 3: smaller cities")
    done = st.slider("Completion percentage", 0, 100, 40, format="%d%%")

    budget = sqft * COST_PER_SQFT[stype] * TIER_COST_FACTOR[tier]
    capex = budget * done / 100
    market_full = sqft * TIER_MARKET_RATE[tier] * (1.15 if stype == "Luxury Villa" else 1.0)
    # asset valued on completed fraction (land/dev premium floor of 25% of land-equivalent value)
    asset_val = market_full * (0.25 + 0.75 * done / 100)
    steel_t = sqft * STEEL_KG_PER_SQFT[stype] / 1000
    cement_bags = sqft * CEMENT_BAGS_PER_SQFT[stype]

    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(metric_card("Total Project Budget", fmt_inr(budget), f"₹{COST_PER_SQFT[stype] * TIER_COST_FACTOR[tier]:,.0f}/sq ft"), unsafe_allow_html=True)
    m2.markdown(metric_card("CapEx Incurred", fmt_inr(capex), f"{done}% of budget"), unsafe_allow_html=True)
    m3.markdown(metric_card("Current Asset Value", fmt_inr(asset_val), "market-based estimate"), unsafe_allow_html=True)
    m4.markdown(metric_card("Value Gain vs CapEx", fmt_inr(max(asset_val - capex, 0)), f"Full value {fmt_inr(market_full)}"), unsafe_allow_html=True)

    st.markdown("")
    r1, r2 = st.columns(2)
    r1.markdown(metric_card("Steel Requirement", f"{steel_t:,.1f} tonnes", f"≈ {steel_t * done / 100:,.1f} t consumed"), unsafe_allow_html=True)
    r2.markdown(metric_card("Cement Requirement", f"{cement_bags:,.0f} bags (50 kg)", f"≈ {cement_bags * done / 100:,.0f} bags consumed"), unsafe_allow_html=True)

    st.markdown("#### Milestone Progress")
    st.progress(done / 100)
    current = [m for p, m in MILESTONES if done >= p][-1]
    nxt = next(((p, m) for p, m in MILESTONES if p > done), None)
    st.write(f"**Current stage:** {current}" + (f"  ·  **Next:** {nxt[1]} at {nxt[0]}%" if nxt else "  ·  🎉 Project complete"))
    mcols = st.columns(len(MILESTONES))
    for col, (p, m) in zip(mcols, MILESTONES):
        col.markdown(f"{'✅' if done >= p else '⬜'}<br><small>{m}<br>{p}%</small>", unsafe_allow_html=True)

    st.markdown("#### 🎨 Conceptual 3D Architectural Rendering")
    style = st.selectbox("Rendering style", ["Photorealistic 3D render", "Modern minimalist", "Indian contemporary", "Blueprint isometric"])
    default_prompt = (f"{style} of a {stype.lower()} building, {sqft} sq ft, {tier} Indian city setting, "
                      f"architectural visualization, golden hour lighting, high detail")
    prompt = st.text_area("Image prompt (editable)", default_prompt, height=80)
    if st.button("🖼️ Generate Concept Render", key="render_btn"):
        st.session_state.render_url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) +
                                       f"?width=1024&height=640&nologo=true&seed={seed_from(prompt.encode(), 99999)}")
    if st.session_state.get("render_url"):
        st.image(st.session_state.render_url, caption="AI concept render via Pollinations (illustrative only)",
                 use_container_width=True)

# ----------------------------------------------------------------------------
# Tab 4 - Weather advisory + chatbot
# ----------------------------------------------------------------------------
with tab4:
    st.subheader("Daily Site Assistant & Weather-Aware Advisory")
    weather = st.radio("Today's site weather", list(WEATHER_ADVISORIES), horizontal=True, key="weather")
    adv = WEATHER_ADVISORIES[weather]
    st.markdown(f"### {adv['icon']} {weather} - Safety Advisory")
    for tone, msg in adv["alerts"]:
        st.markdown(f'<div class="alert-box alert-{tone}">{msg}</div>', unsafe_allow_html=True)

    st.divider()
    st.markdown("### 💬 SiteMate - Engineering Assistant")
    if "chat" not in st.session_state:
        st.session_state.chat = [{"role": "assistant",
                                  "content": "Hi! I'm SiteMate. Ask me about curing, mix design, scaffolding, IS codes or site safety."}]
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if st.button("🗑️ Clear chat", key="clear_chat"):
        st.session_state.pop("chat")
        st.rerun()

    if user_q := st.chat_input("Ask a construction engineering question..."):
        st.session_state.chat.append({"role": "user", "content": user_q})
        with st.chat_message("user"):
            st.markdown(user_q)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    if DEMO:
                        reply = demo_chat_reply(user_q, weather)
                    else:
                        history = [
                            types.Content(role="user" if m["role"] == "user" else "model",
                                          parts=[types.Part(text=m["content"])])
                            for m in st.session_state.chat[1:]  # skip greeting
                        ]
                        resp = client.models.generate_content(
                            model=model_name, contents=history,
                            config=types.GenerateContentConfig(
                                system_instruction=CHAT_SYSTEM.format(weather=weather), temperature=0.4),
                        )
                        reply = resp.text or "I couldn't generate a response. Please rephrase."
                except Exception as e:
                    reply = f"⚠️ Assistant error: {e}"
            st.markdown(reply)
        st.session_state.chat.append({"role": "assistant", "content": reply})
