# 🚀 SENTINEL: Autonomous Spacecraft FDIR Agent

> **SENTINEL** is a Gemini-first, model-agnostic spacecraft safe-mode diagnosis and recovery system. It combines crash-dump parsing, anomaly pre-filtering, RAG-grounded reasoning, safety validation, and auditable causal-chain visualization into an end-to-end FDIR (Fault Detection, Isolation, and Recovery) copilot.

---

## 📖 Overview

Modern spacecraft generate massive amounts of telemetry during a fault. When a spacecraft enters **Safe Mode**, ground operators must manually sift through telemetry to identify the root cause and safely command a recovery. 

**SENTINEL** automates this by:
1. **Ingesting** raw crash dumps and pre-fault telemetry windows.
2. **Detecting** anomalies via statistical Z-score analysis.
3. **Retrieving** standard FDIR procedures using Hybrid RAG over ECSS standards.
4. **Reasoning** over the fault using a Large Language Model (Gemini by default).
5. **Streaming** an auditable reasoning trace (Thought, Action, Observation).
6. **Validating** proposed recovery commands against safety constraints.
7. **Presenting** a rich UI with a Causal DAG and Risk-Assessed Recovery Plan.

---

## 🏗 System Architecture

The project consists of a Python FastAPI backend and a React frontend, communicating via REST and Server-Sent Events (SSE).

### Tech Stack

| Component | Technology | Description |
|-----------|------------|-------------|
| **Core LLM** | Gemini 2.5 Flash | Primary hosted reasoning model for fast inference. |
| **Fallback LLM** | Phi-3-mini / Qwen2.5 | Local models via Ollama for offline/backup modes. |
| **Embeddings** | `sentence-transformers` | Free, local embeddings (`all-MiniLM-L6-v2`). |
| **Vector Database**| ChromaDB | Persistent local storage for document retrieval. |
| **Backend** | FastAPI + Uvicorn | High-performance async API with SSE streaming. |
| **Frontend** | React / HTML / CSS | Real-time dashboard for operators. |

---

## 🧠 Code Flow & Execution Pipeline

The core analysis pipeline is seamlessly orchestrated by the `SentinelAgent` in the backend.

### 1. Data Intake & Validation
When the frontend submits a crash dump (`POST /api/analyze`), the payload is validated against rigorous Pydantic schemas in `sentinel/backend/app/api/models.py`.

### 2. Anomaly Detection
A Z-score statistical detector scans the `pre_fault_telemetry_window`. Parameters deviating significantly from nominal bounds are flagged as anomalies.

### 3. RAG Retrieval
The safe-mode trigger and identified anomalies formulate a search query. ChromaDB fetches relevant procedure snippets from standard **ECSS (European Cooperation for Space Standardization)** manuals. 

### 4. LLM Reasoning
The system compiles the crash dump, anomalies, and RAG context into a prompt. Depending on the configuration, the LLM is queried (Gemini Flash, Tuned Models, or Fallback Models).

### 5. Structured Output & Retry Logic
The LLM is required to return a specific JSON schema (`SentinelOutput`). If the LLM generates malformed JSON, the agent automatically retries with a repair prompt.

### 6. Safety Validation
Before the user sees the recovery commands, a deterministic safety layer evaluates the commands against whitelist rules and physical state constraints. High-risk commands are marked as `BLOCKED` or `HIGH` risk.

### 7. SSE Streaming
Throughout the entire process, intermediate events (`STATUS`, `THOUGHT`, `OBSERVATION`, `RESULT`) are streamed to the frontend via Server-Sent Events (SSE), creating a real-time, typewriter-like transparency trace.

---

## 📂 Directory Structure

```text
SpaceAgent/
├── README.md                              ← This documentation
├── ESA-Mission1/                          ← Raw mission data
├── ESA-Mission1_extracted/                ← Processed mission data
└── sentinel/                              ← The Core Codebase
    ├── backend/                           ← Python FastAPI server
    │   ├── app/                           ← Core application logic
    │   ├── data/                          ← ECSS Manuals and data assets
    │   ├── data_tools/                    ← Tooling for data processing
    │   ├── simulation/                    ← Telemetry generation & simulation
    │   ├── tests/                         ← Test suites
    │   ├── Dockerfile
    │   └── requirements.txt               
    ├── frontend/                          ← Operator Dashboard (React)
    │   ├── public/                        ← Static assets
    │   ├── src/                           ← React components
    │   ├── package.json                   
    │   └── package-lock.json
    ├── notebooks/                         ← Jupyter notebooks for EDA & fine-tuning
    └── docs/                              ← Architecture diagrams and additional documentation
```

---

## 🛠 Setup & Installation

### 1. Environment Setup

Create a virtual environment and install backend dependencies:
```bash
cd sentinel
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

Set up your environment variables:
```bash
cp sentinel/.env.example sentinel/.env
```
Edit `.env` and add your Google Gemini API key:
`GEMINI_API_KEY=your_api_key_here`

### 2. Running the Backend

Launch the FastAPI server on port 8000:
```bash
cd backend
uvicorn app.main:app --reload
```
You can check if it's running by hitting `http://localhost:8000/health`.

### 3. Running the Frontend

In a new terminal window, serve the frontend on port 3000:
```bash
cd sentinel/frontend
npm install
npm run dev
```

Visit `http://localhost:3000` in your browser.

---

## 💡 Usage Examples

### Python API Usage

You can use the Sentinel agent directly in your Python code:

```python
from app.agent.agent import SentinelAgent

# Default uses Gemini Flash + Hybrid RAG
agent = SentinelAgent()

crash_dump_dict = {
    "scenario_id": "TEST_001",
    "fault_type": "ADCS_GYRO_SEU"
}

# This performs retrieval, anomaly detection, reasoning, and safety checks in one go
result = agent.analyze_with_rag(crash_dump_dict)

print(result.model_dump_json(indent=2))
```

### HTTP API Usage

Trigger a crash dump analysis manually via `curl`:

```bash
curl -X POST http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"scenario_id": 1, "fault_type": "ADCS_GYRO_SEU"}'
```

---

## 🛡 Risk Management & Fallbacks

Sentinel is designed with safety and reliability in mind:
- **API Outages**: If the Gemini API is down, the system can seamlessly fall back to local models (e.g. Phi-3) using the `FALLBACK` mode.
- **Hallucination Prevention**: The deterministic safety validator ensures that even if the LLM hallucinated a dangerous command, it would be flagged and blocked before execution.
- **Explainability**: The agent never outputs just a command. It is forced by the Pydantic schema to output 3 distinct hypotheses, confidences, causal chains, and step-by-step rationales.