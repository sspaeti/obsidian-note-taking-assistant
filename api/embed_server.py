"""Embedding server using sentence-transformers BGE-M3."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

app = FastAPI(title="BGE-M3 Embedding Server")

# Allow CORS from Vercel and localhost
allowed_origins = [
    "http://localhost:3000",
    "https://obsidian-rag-teal.vercel.app",
    "https://*.vercel.app",
]

# Add custom origin from env if set
if os.environ.get("ALLOWED_ORIGIN"):
    allowed_origins.append(os.environ["ALLOWED_ORIGIN"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Load model once at startup
print("Loading BGE-M3 model...")
model = SentenceTransformer("BAAI/bge-m3")
print("Model loaded!")


class EmbedRequest(BaseModel):
    text: str


class EmbedResponse(BaseModel):
    embedding: list[float]


@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest):
    """Generate embedding for input text."""
    embedding = model.encode(request.text).tolist()
    return EmbedResponse(embedding=embedding)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "model": "BAAI/bge-m3"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {"service": "BGE-M3 Embedding Server", "endpoints": ["/embed", "/health"]}
