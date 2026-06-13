import asyncio
import json
import logging
from typing import Any, Dict
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent import SentinelAgent
from scenarios import get_preset_scenarios
from models import SSEEvent, SSEEventType

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sentinel.backend")

app = FastAPI(
    title="Sentinel Backend",
    description="A backend API for aerospace crash dump analysis and RAG-powered investigation.",
    version="0.1.0",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = SentinelAgent()

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}

@app.get("/scenarios")
def get_scenarios():
    """Return pre-defined crash dump scenarios for the demo UI."""
    return get_preset_scenarios()

@app.post("/analyze")
async def analyze_endpoint(crash_dump: Dict[str, Any]):
    """Analyze a crash dump and stream reasoning trace + final structured output via SSE."""
    logger.info("Received analysis request for scenario_id: %s", crash_dump.get("scenario_id"))

    async def event_generator():
        try:
            # We call analyze_crash_dump_stream to get the sequence of SSEEvent objects
            for event in agent.analyze_crash_dump_stream(crash_dump):
                # Format event as SSE (data: <json>\n\n)
                yield f"data: {event.model_dump_json()}\n\n"
                
                # Yield a small delay to make thoughts readable in the UI
                if event.event_type in (SSEEventType.THOUGHT, SSEEventType.ACTION, SSEEventType.STATUS):
                    await asyncio.sleep(0.4)
                elif event.event_type == SSEEventType.OBSERVATION:
                    await asyncio.sleep(0.2)
        except Exception as e:
            logger.error("Error during streaming analysis: %s", e, exc_info=True)
            err_event = SSEEvent(
                event_type=SSEEventType.ERROR,
                data=f"Streaming analysis encountered an error: {str(e)}"
            )
            yield f"data: {err_event.model_dump_json()}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")