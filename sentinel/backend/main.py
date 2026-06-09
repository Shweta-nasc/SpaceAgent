from fastapi import FastAPI

app = FastAPI(
    title="Sentinel Backend",
    description="A backend API for aerospace crash dump analysis and RAG-powered investigation.",
    version="0.1.0",
)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/analyze")
def analyze():
    return {"message": "Analysis endpoint placeholder"}
