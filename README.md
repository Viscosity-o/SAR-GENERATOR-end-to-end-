# SAR Generator (End-to-End Autonomous AI Agent Pipeline)

An end-to-end anti-money laundering (AML) Suspicious Activity Report (SAR) generation system driven by a multi-agent orchestration architecture, machine learning classification, PII masking vault, rule-based evidence synthesis, and Groq LLM regulatory drafting.

---

## 🏛 Architecture Overview

1. **Agent 1: Ingestion & Feature Engineering**
   - Ingests raw structured transactions and accounts.
   - Extracts 33 canonical AML features (velocity spikes, cash ratio, structuring thresholds).
   - Runs pre-trained ensemble models (XGBoost & Random Forest) to predict SAR-worthiness, confidence scores, and typologies (Structuring, Layering, Rapid Movement, etc.).

2. **Agent 2: PII Masking & Vault**
   - Cryptographically tokenizes sensitive PII (names, SSNs, account numbers, addresses) into clean deterministic tokens (`[NAME_1]`, `[ACCOUNT_1]`).
   - Stores mapping securely in a local PostgreSQL PII masking vault table.

3. **Agent 3: Evidence & Rules Engine**
   - Evaluates 8 deterministic AML rules (structuring near $10k FinCEN threshold, counterparty fragmentation, round-trip velocity, etc.).

4. **Agent 4: Compliance Validation**
   - Checks against SAR filing regulations (31 U.S.C. 5318(g), FinCEN advisories, FATF standards).

5. **Agent 5: Narrative Synthesis (Groq LLM)**
   - Assembles full case context tree, rule firings, and regulatory guidance citations.
   - Uses Groq (`llama-3.3-70b-versatile`) to generate a formal, audit-ready 5-section FinCEN SAR narrative.

---

## 🛠 Tech Stack

- **Backend**: FastAPI, Python 3.11+, Pydantic, Uvicorn, LangGraph, Psycopg2
- **ML / Data**: XGBoost, Scikit-learn (RandomForest), Pandas, NumPy, Joblib
- **LLM / AI**: Groq Cloud SDK (`llama-3.3-70b-versatile`)
- **Database / Storage**: PostgreSQL, Supabase
- **Frontend**: React, Vite, Claude-inspired Warm Minimalist Design System

---

## 🚀 Setup & Installation

### 1. Backend Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the root directory:
```env
GROQ_API_KEY="your-groq-api-key"
DATABASE_URL="postgresql://user:password@localhost:5432/postgres"
SUPABASE_URL="your-supabase-url"
SUPABASE_KEY="your-supabase-key"
```

Start backend:
```bash
uvicorn backend.main:app --reload --port 8000
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173).
