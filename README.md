# 🏗️ Multimodal Construction Intelligence Platform

**Skill Wallet Capstone Project 1** · NASSCOM FutureSkills Prime

An AI-powered Streamlit application that combines multimodal vision analysis (Google Gemini), a rule-based valuation engine and a weather-aware engineering assistant for construction sites.

**Live demo:** https://construction-intelligence-platform-j9d7qxofu9vsignqupnlbt.streamlit.app/

---

## Features

| Tab | What it does |
|---|---|
| 🦺 **Site Safety & PPE Audit** | Upload a site photo. Gemini checks helmets, high-vis vests, steel-toe boots and safety harnesses against OSHA 29 CFR 1926 and IS codes, and returns structured JSON: `safety_score` (0-100), `overall_status`, PPE checklist and hazards with severity (Low/Medium/High/Critical) and remedies. Downloadable JSON report. |
| 🧱 **Crack Diagnostics** | Upload a concrete/wall photo. Classifies the defect (Hairline, Settlement, Structural Shear, Thermal Expansion, Spalling), estimates crack width (mm), lists root causes, recommended repairs (e.g. epoxy injection, structural re-grouting) and urgency. |
| 💰 **Planning & Valuation** | Inputs: structure type, built-up area, city tier (1/2/3), completion %. Outputs: total budget, CapEx incurred, current asset value (INR Lakhs/Crores), steel and cement requirements, milestone progress. Conceptual 3D render via Pollinations AI. |
| 🌦️ **Site Assistant** | Weather selector (High Wind, Heavy Rain, Extreme Heat, Normal) with dynamic safety alerts, plus a multi-turn engineering chatbot. |

The sidebar accepts a Gemini API key. Without a key the app runs in **demo mode** with sample outputs.

## Architecture

```
Streamlit UI (tabs, custom CSS)
   ├── Vision AI: Gemini multimodal (image + structured-JSON prompt, auto-retry on 503/429)
   ├── Valuation: deterministic rule-based cost model (INR)
   ├── Rendering: Pollinations AI image URL
   ├── Chat: Gemini with engineering system prompt + weather context
   └── State: st.session_state only (no external database)
```

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push `app.py`, `requirements.txt` and `README.md` to a public GitHub repo.
2. At share.streamlit.io choose **Create app**, select the repo, branch `main`, main file `app.py`.
3. Optional: add `GEMINI_API_KEY = "your-key"` under **Settings → Secrets**. Never commit keys to the repo.

## Standards referenced

OSHA 29 CFR 1926 · IS 456:2000 · IS 7969 · IS 3764 · IS 13935 · ACI 224R

## Limitations

- AI output is advisory and not a substitute for a licensed safety officer or structural engineer.
- Crack width is estimated visually from a photo and is approximate.
- Valuation uses illustrative average rates (see constants at the top of `app.py`); it is not a certified valuation.
- Free-tier Gemini keys can return temporary 429/503 errors; the app retries automatically.

## Tech stack

Python · Streamlit · Google Gemini (`google-genai`) · Pollinations AI
