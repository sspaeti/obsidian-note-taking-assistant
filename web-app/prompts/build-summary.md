# Building the Second Brain RAG Web App with Claude Code

This document summarizes how the web app was built using Claude Code (AI agent) in a single session.

## Initial Prompt / Plan

The session started with a [detailed implementation](agents-webapp.md) plan specifying:
- Goal: Create a minimal, blog-friendly web app to query a Second Brain hosted on MotherDuck
- Existing data: Local DuckDB with notes, chunks, embeddings (1024-dim BGE-M3), links, hyperedges
- Key constraint: MotherDuck doesn't support VSS extension, so manual cosine similarity needed

## What Claude Code Built

### 1. Data Sync to MotherDuck
- Uploaded all tables from local `second_brain.duckdb` to MotherDuck cloud
- Created `make sync-motherduck` command for future syncs

### 2. Next.js Web App (`web-app/`)
- Created Next.js app with TypeScript + Tailwind
- Installed `@motherduck/wasm-client` for browser-based DuckDB
- Configured CORS headers for WASM SharedArrayBuffer

### 3. MotherDuck Client (`lib/motherduck.ts`)
Functions implemented:
- `listNotes()` - Browse all notes
- `searchNotesByTitle()` - Search by title
- `getBacklinks()` / `getForwardLinks()` - Graph traversal
- `getConnections()` - N-hop graph exploration
- `getSharedTags()` - Hyperedge queries
- `semanticSearch()` - Manual cosine similarity on embeddings
- `findHiddenConnections()` - Semantically similar but unlinked notes

### 4. Embedding Server (`api/`)
- FastAPI server with BGE-M3 model
- Lazy loading to pass Railway healthchecks
- Dockerfile for Railway deployment

### 5. Main UI (`app/page.tsx`)
Three tabs:
- **Browse & Links**: List notes, view backlinks/forward links, connections, shared tags
- **Semantic Search**: Query by meaning using embeddings
- **Hidden Connections**: Find related but unlinked notes

Clickable links to public brain at `ssp.sh/brain/[note-name]`

## Challenges & Solutions

| Challenge | Solution |
|-----------|----------|
| MotherDuck no VSS extension | Manual cosine similarity in SQL |
| HuggingFace API rate limits / BGE-M3 too large | Self-hosted FastAPI on Railway |
| Railway healthcheck failures | Lazy model loading (load on first request) |
| WASM Worker SSR errors | Dynamic import for MDConnection |
| `lib/` folder gitignored | Changed `.gitignore` from `lib/` to `/lib/` |
| Duplicate tags causing constraint errors | Added `set()` deduplication in ingestion |
| MotherDuck WASM requires auth | Token required even for shared databases |

## Final Architecture

```
┌─────────────────────────────────────────────────────┐
│                 USER'S BROWSER                      │
│  Next.js + MotherDuck WASM Client                   │
│  - Browse notes, links, connections                 │
│  - Semantic search UI                               │
│  - Hidden connections discovery                     │
└─────────────┬───────────────────────┬───────────────┘
              │                       │
   WebSocket  │                       │ HTTP POST
   (SQL)      │                       │ (embed text)
              ▼                       ▼
┌─────────────────────────┐  ┌────────────────────────┐
│   MOTHERDUCK CLOUD      │  │   RAILWAY              │
│   Database: obsidian_rag│  │   FastAPI + BGE-M3     │
│   Tables: notes, chunks,│  │   /embed endpoint      │
│   embeddings, links,    │  │   1024-dim vectors     │
│   hyperedges            │  │                        │
└─────────────────────────┘  └────────────────────────┘
```

## Deployment

- **Frontend**: Vercel (auto-deploy from GitHub)
- **Embedding Server**: Railway (Dockerfile in `api/`)
- **Database**: MotherDuck (synced via `make sync-motherduck`)

## Key Files Created

| File | Purpose |
|------|---------|
| `web-app/lib/motherduck.ts` | All MotherDuck queries |
| `web-app/app/page.tsx` | Main UI with 3 tabs |
| `web-app/app/api/embed/route.ts` | Proxy to embedding server |
| `api/embed_server.py` | FastAPI BGE-M3 server |
| `api/Dockerfile` | Railway deployment |
| `Makefile` | All dev/deploy commands |

## Session Stats

- Duration: ~2-3 hours of interaction
- Files created/modified: ~15
- Deployments: Vercel (frontend) + Railway (API)
- Key technologies: Next.js, MotherDuck WASM, FastAPI, BGE-M3, DuckDB

## Learnings for AI-Assisted Development

1. **Plan mode is powerful** - Starting with a detailed plan helped Claude understand the full architecture
2. **Iterative debugging** - Many issues (healthchecks, CORS, auth) required back-and-forth
3. **Human decisions still needed** - Architecture choices, domain names, security trade-offs
4. **Context limits** - Session was compacted due to length, but continued seamlessly
5. **Real deployment complexity** - Local dev vs production differences (tokens, URLs, environment)
