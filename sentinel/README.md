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
| Orchestration | Simple function chain (LangGraph-ready) | Hackathon-safe |

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
├── .gitignore
├── .env.example          ← GEMINI_API_KEY=your_gemini_key_here
├── backend/
│   ├── main.py           ← FastAPI app (Steps 4+5+6 pipeline wired)
│   ├── agent.py          ← Gemini-first reasoning agent
│   ├── models.py         ← Pydantic output schema (SentinelOutput)
│   ├── prompts.py        ← Master system prompt + builders
│   ├── rag.py            ← Hybrid RAG (PDF RAG + fallback KB)
│   ├── simulator.py      ← Crash dump generator (SENTINEL schema)
│   ├── evaluator.py      ← 8-metric evaluation harness
│   ├── requirements.txt
│   ├── Dockerfile
│   └── data/ecss/        ← ECSS PDF standards
├── frontend/             ← React application
├── notebooks/            ← Kaggle fine-tuning notebooks
└── docs/                 ← Architecture diagrams
```

## Step Status

| Step | Description | Status |
|---|---|---|
| 1 | Pydantic output schema (`models.py`) | ✅ Complete |
| 2 | Master system prompt (`prompts.py`) | ✅ Complete |
| 3 | Agent skeleton (`agent.py`) | ✅ Complete |
| 4 | Fallback KB retrieval (`rag.py`) | ✅ Complete |
| 5 | Structured output validation (`models.py` + agent retry) | ✅ Complete |
| 6 | PDF RAG integration (`rag.py` + ChromaDB) | ✅ Complete |
| 7 | Safety command whitelist (`safety.py`) | ❌ Not yet built |
| 9+ | LangGraph tool routing | ❌ Future |
| 11 | SSE streaming endpoint | ❌ Future |

## Setup

```bash
pip install -r backend/requirements.txt
```

Or manually:

```bash
pip install google-genai fastapi uvicorn pydantic python-dotenv
pip install sentence-transformers chromadb llama-index
pip install numpy scipy httpx
```

### Environment

```bash
cp .env.example .env
# Edit .env and add your Gemini API key:
# GEMINI_API_KEY=your_gemini_key_here
```

### Verify

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

```python
from agent import SentinelAgent, AgentConfig, ModelMode

# Default: Gemini Flash + RAG (Steps 4+5+6 in one call)
agent = SentinelAgent()
result = agent.analyze_with_rag(crash_dump_dict)
print(result.model_dump_json(indent=2))

# Or manual: retrieve first, then analyze
from rag import retrieve_procedures
procedures = retrieve_procedures(query="gyro SEU fault", fault_cues=["GYRO_A_RATE"])
result = agent.analyze_crash_dump(crash_dump_dict, retrieved_procedures=procedures)

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
cd backend && uvicorn main:app --reload

# Submit a crash dump
curl -X POST http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"crash_dump": {"scenario_id": "TEST_001", "fault_type": "ADCS_SENSOR_FAULT", ...}}'

# Health check
curl http://localhost:8000/health

# RAG status
curl http://localhost:8000/rag/status
```

## Risks

| Risk | Mitigation | Fallback |
|---|---|---|
| Gemini API quota/rate limit | Pre-cache demo scenarios, tight prompts | Cached responses or local model |
| Hosted model latency | Use Gemini Flash, reduce chunks | Cache reasoning, stream saved events |
| Provider unavailable | Keep local model path ready | Phi-3-mini / Qwen2.5 or cached demo |
