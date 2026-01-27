# Second Brain RAG - Web App

Browser-based interface to query your Second Brain hosted on MotherDuck.

## Setup

```bash
# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# Edit .env.local with your tokens:
# - NEXT_PUBLIC_MOTHERDUCK_TOKEN (read-only token from MotherDuck)
# - EMBED_API_URL (Railway embedding server URL)
```

## Development

```bash
# Start embedding server (for semantic search)
cd ../api && uvicorn embed_server:app --port 8001

# Start web app
npm run dev
```

Or use Makefile from parent directory:
```bash
make embed-server  # Terminal 1
make web-dev       # Terminal 2
```

## Deployment

- **Frontend**: Deploy to Vercel, add env vars in project settings
- **Embedding Server**: Deploy `/api` folder to Railway

## Architecture

```
Browser (Next.js + MotherDuck WASM)
    ├── Direct SQL queries → MotherDuck Cloud
    └── /api/embed route → Railway (FastAPI + BGE-M3)
```
