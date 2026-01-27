"""Embedding server using sentence-transformers BGE-M3."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Global model reference (loaded lazily)
model = None


def get_model():
    """Load model on first use (lazy loading)."""
    global model
    if model is None:
        print("Loading BGE-M3 model...")
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("BAAI/bge-m3")
        print("Model loaded!")
    return model


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: just log, don't load model yet
    print("Server starting...")
    yield
    # Shutdown
    print("Server shutting down...")


app = FastAPI(title="BGE-M3 Embedding Server", lifespan=lifespan)

# Allow CORS from Vercel and localhost
allowed_origins = [
    "http://localhost:3000",
    "https://obsidian-rag-teal.vercel.app",
]

# Add custom origin from env if set
if os.environ.get("ALLOWED_ORIGIN"):
    allowed_origins.append(os.environ["ALLOWED_ORIGIN"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


class EmbedRequest(BaseModel):
    text: str


class EmbedResponse(BaseModel):
    embedding: list[float]


@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest):
    """Generate embedding for input text."""
    try:
        m = get_model()  # Loads on first request
        embedding = m.encode(request.text).tolist()
        return EmbedResponse(embedding=embedding)
    except Exception as e:
        print(f"Embedding error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint - returns OK immediately (model loads lazily)."""
    return {"status": "ok", "model": "BAAI/bge-m3", "loaded": model is not None}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "BGE-M3 Embedding Server",
        "model_loaded": model is not None,
        "endpoints": ["/embed", "/health"],
    }
