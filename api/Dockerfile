FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the model during build (faster cold starts)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"

# Copy application
COPY embed_server.py .

# Default port (Railway overrides via PORT env)
ENV PORT=8080

# Use shell form with explicit bash to expand variables
CMD ["/bin/sh", "-c", "uvicorn embed_server:app --host 0.0.0.0 --port ${PORT}"]
