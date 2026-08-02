# 🤖 Spandan AI Symptom Checker & Medical Triage Engine — Architecture & Guide

This document explains the internal design, workflow, and configuration of **Spandan's AI Symptom Triage System** located in [`backend/app/services/ai.py`](file:///backend/app/services/ai.py).

---

## 🏗️ 3-Tier Hybrid Triage Architecture

To guarantee both **patient safety** (zero latency for critical emergencies) and **high accuracy** (even during internet outages or missing API keys), Spandan uses a hybrid 3-tier triage architecture:

```
[ Patient Enters Symptoms ]
           │
           ▼
Tier 1: Rule-Based Emergency Engine (Local 0ms Screening)
           │
           ├─► If Life-Threatening Keyword Found ──► [ INSTANT EMERGENCY ALERT & AMBULANCE INSTRUCTIONS ]
           │
           ▼ (If Non-Emergency)
Tier 2: Groq Cloud AI Engine (Ultra-Fast LLM Inference)
           │
           ├─► Calls Groq API (llama-3.3-70b-versatile) with Structured Medical Prompt & DB Specializations
           ├─► Returns Strict JSON (Recommended Doctor, Urgency, Reasoning & Self-Care Monitoring)
           │
           ▼ (If API Key Missing / Network Disconnected / API Error)
Tier 3: Local Keyword Fallback Engine (Automated Backup Matrix)
           │
           └─► High-Accuracy Keyword Matrix (Cardiology, Orthopedics, Pediatrics, Dermatology, etc.)
```

---

## 🔬 Detailed Breakdown of the 3 Tiers

### 1️⃣ Tier 1: 0ms Rule-Based Emergency Screening (Local & Instant)
Before making any cloud requests, every symptom text is screened locally against a comprehensive list of life-threatening emergency keywords:
* **Keywords**: `chest pain`, `severe breathing difficulty`, `shortness of breath severe`, `stroke`, `slurred speech`, `sudden weakness`, `unconscious`, `fainting`, `severe bleeding`, `heart attack`, `coughing blood`, `blue lips`, `seizure`, `unresponsive`, `anaphylaxis`.
* **Why local screening?** If a patient is experiencing a heart attack or stroke, relying on a cloud LLM is dangerous due to potential network latency or API timeouts.
* **Result**: If triggered, Spandan instantly bypasses the LLM and returns an `EMERGENCY` recommendation instructing the patient to call emergency services (`999` in Bangladesh) and go directly to the nearest hospital Emergency Room.

### 2️⃣ Tier 2: Groq Cloud AI Engine (`llama-3.3-70b-versatile`)
If no emergency keywords are detected, Spandan invokes the **Groq Cloud API** (`https://api.groq.com/openai/v1/chat/completions`) for deep symptom analysis.
* **Dynamic Database Context**: Spandan queries your PostgreSQL database for all currently active doctor specializations (`Cardiology`, `Neurology`, `Pediatrics`, `Orthopedics`, `General Medicine`, etc.) and injects them into the system prompt.
* **Structured JSON Output**: The LLM is instructed to return strictly formatted JSON containing:
  * `recommended_specialization_name`: Exact match to a database specialty so the user can immediately click **"Book [Specialty] Doctor"**.
  * `alternative_specialization_name`: A secondary medical specialty if relevant.
  * `urgency_level`: Categorized as `routine`, `soon`, or `urgent`.
  * `reasoning_summary`: A concise 2-3 sentence clinical explanation for why this specialist is appropriate.
  * `safety_message`: Customized self-care advice and symptoms to watch out for while waiting for the appointment.

### 3️⃣ Tier 3: Local Automated Fallback Engine (`_get_fallback_triage`)
If `GROQ_API_KEY` is not set (`your_groq_api_key_here` or empty), or if a cloud network error/timeout occurs, Spandan seamlessly falls back to an internal medical keyword matrix right inside the Python backend:
* **Cardiology**: Triggered by keywords like `heart`, `palpitation`, `pressure`, `pulse`.
* **Orthopedics**: Triggered by keywords like `bone`, `joint`, `fracture`, `knee`, `back pain`, `spine`.
* **Pediatrics**: Triggered by keywords like `child`, `infant`, `baby`, `kid`.
* **Dermatology**: Triggered by keywords like `skin`, `rash`, `itch`, `acne`.
* **Neurology**: Triggered by keywords like `headache`, `migraine`, `dizzy`, `numb`.
* **General Medicine**: Default routing if no specific organ system keywords dominate.

---

## 🔑 Did We Use a Groq API Key or is it Currently Empty?

Currently, the `GROQ_API_KEY` in `docker-compose.yml` defaults to the placeholder:
```yaml
GROQ_API_KEY: ${GROQ_API_KEY:-your_groq_api_key_here}
```
Because the key is set to `"your_groq_api_key_here"`, Spandan automatically detects that no live API key has been provided yet, and smoothly runs **Tier 3 (Automated Fallback Engine)** for all non-emergency symptom checks. This means your symptom checker works right now out-of-the-box without needing any external credentials!

---

## ⚙️ How to Connect Your Real Groq API Key

If you want Spandan to use live **Groq AI (`llama-3.3-70b-versatile`)** instead of the automated fallback:

1. **Get a Free API Key**: Visit [https://console.groq.com/keys](https://console.groq.com/keys) and generate a free API key.
2. **Add it to your environment**:
   Create a `.env` file in the project root (next to `docker-compose.yml`) or inside `backend/.env` with:
   ```env
   GROQ_API_KEY=gsk_your_actual_groq_api_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   ```
3. **Restart the backend container**:
   ```bash
   docker compose restart backend
   ```
That's it! The next time a patient checks symptoms, Spandan will dynamically query Groq's cloud LPU inference engine in real time.
