# Second Brain RAG

Local-first knowledge retrieval system for Obsidian notes using DuckDB with vector search.


## Features

- **Semantic search**: Find notes by meaning using BGE-M3 embeddings (1024-dim)
- **Backlinks**: Find all notes linking to a specific note
- **Graph traversal**: Discover notes N hops away via wikilinks
- **Hidden connections**: Surface semantically similar notes that aren't directly linked
- **Shared tags (Hyperedge)**: Find notes sharing multiple tags via hyperedge graph
- **Graph-boosted search**: Combine semantic similarity with graph connectivity
- **Your notes never leave your machine**: Everything runs locally with DuckDB and [`BAAI/bge-m3`](https://huggingface.co/BAAI/bge-m3) embedding model.

## Setup

```bash
# Install dependencies
uv sync

# Configure your vault path
cp .env.example .env
# Edit .env and set VAULT_PATH to your Obsidian vault location
```

**.env configuration:**
```bash
# Path to your Obsidian vault
VAULT_PATH=/path/to/your/obsidian/vault

# Database file location (default: second_brain.duckdb)
DB_PATH=second_brain.duckdb
```

## Usage

### Ingest your vault

```bash
make ingest
# or pass path directly:
uv run python scripts/ingest.py /path/to/obsidian/vault
```

### Query

```bash
# Semantic search
uv run python scripts/query.py semantic "data modeling best practices" --limit 10

# Find backlinks
uv run python scripts/query.py backlinks "note-slug"

# Graph connections (1-3 hops)
uv run python scripts/query.py connections "note-slug" --hops 2

# Hidden connections (similar but unlinked)
uv run python scripts/query.py hidden "search query" --seed "note-slug"

# Shared tags (hyperedge query) - find notes sharing 2+ tags
uv run python scripts/query.py shared-tags "note-slug" --min-shared 2

# Graph-boosted search - semantic + graph connectivity boost
uv run python scripts/query.py graph-boosted "search query" --seed "note-slug" --boost 1.2

# Raw SQL
uv run python scripts/query.py sql "SELECT title, slug FROM notes LIMIT 10"
```

### Test queries

```bash
make test-all   # Run all test queries
make stats      # Show database statistics
```

## Database Schema

| Table             | Description                              |
|-------------------|------------------------------------------|
| notes             | Note metadata, content, frontmatter      |
| links             | Wikilink graph edges                     |
| chunks            | Chunked content for RAG retrieval        |
| embeddings        | 1024-dim vectors (BAAI/bge-m3)           |
| hyperedges        | Multiway relations (tags, folders)       |
| hyperedge_members | Note membership in hyperedges            |

## Tech Stack

- DuckDB with VSS extension (vector similarity search)
- sentence-transformers for embeddings
- Python 3.11+

## How Embeddings and Connections are Identified

The system uses **two distinct data sources** that are combined in different ways:

### Data Source 1: Wikilinks (Graph)

During ingestion, the parser extracts all `[[wikilinks]]` from your Obsidian notes using regex:

```
[[Target Note]]           → link from current note to "target-note"
[[Target Note|display]]   → same, with custom display text
[[Note#Section]]          → link with heading anchor (anchor stripped)
```

These are stored in the `links` table as directed edges:
```
source_slug: "my-note"  →  target_slug: "target-note"
```

This creates a **graph** of your knowledge base based on explicit connections you made.

### Data Source 2: Embeddings (Semantic)

Each note is split into chunks (~512 tokens), and each chunk is converted to a 384-dimensional vector using `all-MiniLM-L6-v2`. These vectors capture semantic meaning - similar concepts have vectors that are close together in vector space.

```
"functional programming principles" → [0.23, -0.45, 0.12, ...]  (384 floats)
"FP best practices in Python"       → [0.21, -0.42, 0.15, ...]  (similar vector)
```

DuckDB's VSS extension with HNSW index enables fast cosine similarity search across all embeddings.

---

### Query Type Breakdown

#### 1. Backlinks (Graph only)

**How it works:** Pure SQL query on the `links` table - finds all notes where `target_slug` matches your query.

**Example:**
```bash
uv run python scripts/query.py backlinks "functional-data-engineering"
```

```sql
SELECT source_slug, link_text FROM links
WHERE target_slug = 'functional-data-engineering'
```

**Result:** Notes that explicitly link to Functional Data Engineering:
- Python → linked as "Functional Data Engineering"
- Maxime Beauchemin → linked as "Functional Data Engineering"
- Idempotency → linked as "Functional Data Engineering"

These are connections **you made** via `[[Functional Data Engineering]]` wikilinks.

---

#### 2. Connections (Graph only)

**How it works:** Recursive graph traversal using SQL CTE. Follows wikilink edges N hops from a starting note.

**Example:**
```bash
uv run python scripts/query.py connections "python" --hops 2
```

```sql
WITH RECURSIVE connected AS (
    SELECT target_slug, 1 as hop FROM links WHERE source_slug = 'python'
    UNION
    SELECT l.target_slug, c.hop + 1 FROM connected c
    JOIN links l ON l.source_slug = c.slug WHERE c.hop < 2
)
SELECT DISTINCT slug, hop FROM connected
```

**Result:**
- Hop 1: Notes that Python links to (Functional Data Engineering, Data Engineering, etc.)
- Hop 2: Notes those link to (Airflow, Dagster, etc.)

No embeddings involved - purely following your wikilink graph.

---

#### 3. Semantic Search (Embeddings only)

**How it works:**
1. Your query text is embedded into a 384-dim vector
2. DuckDB finds chunks with highest cosine similarity via HNSW index
3. Returns notes containing those chunks

**Example:**
```bash
uv run python scripts/query.py semantic "data modeling best practices"
```

```sql
SELECT title, 1 - array_cosine_distance(embedding, $query_vector) as similarity
FROM embeddings e JOIN chunks c ON c.chunk_id = e.chunk_id
ORDER BY similarity DESC
```

**Result:** Notes semantically similar to "data modeling best practices":
- Data Modeling: The Unsung Hero (similarity: 0.75)
- Semantic Layer (similarity: 0.69)
- Kimball Dimensional Modeling (similarity: 0.65)

These notes match by **meaning**, not by explicit links. A note about "dimensional modeling techniques" matches even if it never mentions "best practices".

---

#### 4. Hidden Connections (Embeddings + Graph combined)

**How it works:** This is the most interesting query - it combines both data sources:
1. Find semantically similar notes (embeddings)
2. Filter OUT notes that are already linked (graph)
3. What remains = notes you **should probably link** but haven't

**Example:**
```bash
uv run python scripts/query.py hidden "Python pipelines" --seed "functional-data-engineering"
```

```sql
WITH semantic_similar AS (
    -- Find notes similar to "Python pipelines" via embeddings
    SELECT slug, similarity FROM embeddings WHERE similarity > 0.4
),
direct_links AS (
    -- Get all notes already linked to/from the seed note
    SELECT target_slug FROM links WHERE source_slug = 'functional-data-engineering'
    UNION
    SELECT source_slug FROM links WHERE target_slug = 'functional-data-engineering'
)
-- Return similar notes that are NOT linked
SELECT * FROM semantic_similar
WHERE slug NOT IN (SELECT * FROM direct_links)
```

**Result:** Notes about Python pipelines that aren't linked to Functional Data Engineering:
- Orchestration (similarity: 0.63) - not linked!
- Pipeline Evolution (similarity: 0.61) - not linked!
- Python for Data Engineers (similarity: 0.59) - not linked!

These are **discovery suggestions** - semantically related content you might want to connect.

---

### Summary Table

| Query Type | Data Source | Use Case |
|------------|-------------|----------|
| Backlinks | Wikilinks (graph) | "What links to this note?" |
| Connections | Wikilinks (graph) | "What's N hops away in my graph?" |
| Semantic | Embeddings (vectors) | "Find notes about this topic" |
| Hidden | Both combined | "What should I link but haven't?" |
| Shared Tags | Hyperedges | "Notes sharing multiple tags with this one" |
| Graph-Boosted | Embeddings + Graph | "Semantic search boosted by graph proximity" |


## 100% Local & Private

**Your notes never leave your machine.** Everything runs locally:

| Component | Where it runs |
|-----------|---------------|
| Embedding model | Local CPU (sentence-transformers) |
| Vector database | Local file (DuckDB) |
| All queries | Local |

Unlike OpenAI/Anthropic APIs that send your text to the cloud, the `BAAI/bge-m3` (replace with any model you like) embedding model runs entirely in-process on your machine. This makes it safe for:
- Personal journals and private notes
- Confidential work documents
- Sensitive research materials
- Anything you wouldn't want uploaded to a third party

**Network activity:**
- One-time model download (~1.8GB from Hugging Face) on first run
- After that: zero network activity, works fully offline

```bash
# Pre-download model for offline use
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
```
