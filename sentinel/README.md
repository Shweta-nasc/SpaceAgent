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
│   ├── main.py           ← FastAPI app
│   ├── agent.py          ← Gemini-first reasoning agent
│   ├── models.py         ← Pydantic output schema (SentinelOutput)
│   ├── prompts.py        ← Master system prompt + builders
│   ├── rag.py            ← Hybrid RAG (PDF + fallback KB)
│   ├── simulator.py      ← Crash dump simulator (placeholder)
│   ├── evaluator.py      ← Evaluation harness (placeholder)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── data/ecss/        ← ECSS PDF standards
├── frontend/             ← React application
├── notebooks/            ← Kaggle fine-tuning notebooks
├── demo_cache/           ← Pre-computed demo responses
├── evaluation/           ← Evaluation results
└── docs/                 ← Architecture diagrams
```

## Setup

```bash
python -m venv sentinel-env
source sentinel-env/bin/activate
pip install google-genai langchain langgraph llama-index chromadb
pip install fastapi uvicorn pydantic numpy scipy httpx python-dotenv
pip install sentence-transformers
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

# Default: Gemini Flash
agent = SentinelAgent()
result = agent.analyze_crash_dump(crash_dump_dict)
print(result.model_dump_json(indent=2))

# Tuned model
config = AgentConfig(mode=ModelMode.TUNED, tuned_model_id="tunedModels/sentinel-v1")
agent = SentinelAgent(config)

# Fallback (local Phi-3-mini via Ollama)
config = AgentConfig(mode=ModelMode.FALLBACK)
agent = SentinelAgent(config)
```

## Risks

| Risk | Mitigation | Fallback |
|---|---|---|
| Gemini API quota/rate limit | Pre-cache demo scenarios, tight prompts | Cached responses or local model |
| Hosted model latency | Use Gemini Flash, reduce chunks | Cache reasoning, stream saved events |
| Provider unavailable | Keep local model path ready | Phi-3-mini / Qwen2.5 or cached demo |
