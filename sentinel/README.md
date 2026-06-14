# SENTINEL

> SENTINEL is a Gemini-first, model-agnostic spacecraft safe-mode diagnosis and recovery system that combines crash-dump parsing, anomaly pre-filtering, RAG-grounded reasoning, safety validation, and auditable causal-chain visualization.

## Architecture

SENTINEL uses a **Gemini-first, model-agnostic architecture**. Gemini Flash is the primary hosted reasoning model for live demo inference, while Phi-3-mini or Qwen2.5 provide free/local fallback and experimentation paths. Retrieval is grounded in ECSS engineering documents using ChromaDB with free/local embeddings (sentence-transformers), and every model output passes through structured validation, safety checks, and auditable causal-chain rendering before presentation.

### Tech Stack

| Layer | Technology | Why |
|---|---|---|
| LLM (demo) | Gemini Flash | Fast, strong reasoning, easy hosted inference |
| LLM (free/local fallback) | Phi-3-mini / Qwen2.5 | Free, Kaggle/local experimentation |
| LLM (fine-tuned) | Phi-3-mini via Unsloth | Best fit for Kaggle QLoRA workflow |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` | Free, local, no API key needed |
| Vector store | ChromaDB | Local persistent mode |
| RAG framework | LlamaIndex | PDF loading and chunking |
| Backend | FastAPI + Uvicorn | Lightweight, async-ready |
| Frontend | React + Vite | Fast dev server |

### Reasoning Modes

The agent supports three selectable modes in one pipeline:

| Mode | Model | Use Case |
|---|---|---|
| `base` | Gemini Flash | Primary demo path, live inference |
| `tuned` | Tuned Gemini / fine-tuned endpoint | More stable repeated fault diagnosis |
| `fallback` | Phi-3-mini / Qwen2.5 via Ollama | Offline backup, evaluation comparison |

## Structure

```text
sentinel/
├── README.md
├── .env.example          ← GEMINI_API_KEY=your_gemini_key_here
├── backend/              ← Core Python API and reasoning logic
│   ├── app/              
│   │   ├── main.py       ← FastAPI app entrypoint
│   │   ├── agent/        ← Gemini-first reasoning agent
│   │   ├── analytics/    ← Anomaly detection
│   │   └── api/          ← Routes and models (Pydantic schema)
│   ├── data/             ← ECSS PDF standards & ChromaDB store
│   ├── simulation/       ← Telemetry generation
│   ├── tests/            ← Unit and integration tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/             ← Real-time operator dashboard
│   ├── public/
│   ├── src/
│   └── package.json
├── notebooks/            ← Kaggle/Jupyter fine-tuning & EDA notebooks
└── docs/                 ← Architecture diagrams
```

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
```

### Environment

```bash
cp .env.example .env
# Edit .env and add your Gemini API key:
# GEMINI_API_KEY=your_gemini_key_here
```

### Verify Gemini

```python
from google import genai
import os
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Reply with: OK"
)
print(resp.text)
```

## Usage

### Core Python Pipeline

```python
from app.agent.agent import SentinelAgent, AgentConfig, ModelMode

# Default: Gemini Flash + RAG
agent = SentinelAgent()
result = agent.analyze_with_rag(crash_dump_dict)
print(result.model_dump_json(indent=2))

# Tuned model
config = AgentConfig(mode=ModelMode.TUNED, tuned_model_id="tunedModels/sentinel-v1")
agent = SentinelAgent(config)

# Fallback (local Phi-3-mini via Ollama)
config = AgentConfig(mode=ModelMode.FALLBACK)
agent = SentinelAgent(config)
```

### HTTP API

```bash
# Start the server
cd backend && uvicorn app.main:app --reload

# Submit a crash dump
curl -X POST http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"crash_dump": {"scenario_id": "TEST_001", "fault_type": "ADCS_GYRO_SEU", ...}}'

# Health check
curl http://localhost:8000/health
```

## Risks

| Risk | Mitigation | Fallback |
|---|---|---|
| Gemini API quota/rate limit | Pre-cache demo scenarios, tight prompts | Cached responses or local model |
| Hosted model latency | Use Gemini Flash, reduce chunks | Cache reasoning, stream saved events |
| Provider unavailable | Keep local model path ready | Phi-3-mini / Qwen2.5 or cached demo |
