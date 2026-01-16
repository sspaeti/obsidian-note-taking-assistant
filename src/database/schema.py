"""DuckDB schema initialization with VSS extension."""
import duckdb

# Model configurations: model_name -> embedding_dimension
MODEL_CONFIGS = {
    'all-MiniLM-L6-v2': 384,
    'BAAI/bge-m3': 1024,
    'BAAI/bge-small-en-v1.5': 384,
    'BAAI/bge-base-en-v1.5': 768,
    'BAAI/bge-large-en-v1.5': 1024,
}

DEFAULT_MODEL = 'all-MiniLM-L6-v2'  # Fast default for testing


def get_embedding_dim(model_name: str) -> int:
    """Get embedding dimension for a model."""
    if model_name in MODEL_CONFIGS:
        return MODEL_CONFIGS[model_name]
    # For unknown models, we'll detect at runtime
    return None


def get_schema_sql(embedding_dim: int, model_name: str) -> str:
    """Generate schema SQL with correct embedding dimension."""
    return f"""
-- Notes table: main note metadata and content
CREATE TABLE IF NOT EXISTS notes (
    note_id INTEGER PRIMARY KEY,
    file_path VARCHAR NOT NULL UNIQUE,
    slug VARCHAR NOT NULL UNIQUE,
    title VARCHAR,
    content TEXT,
    frontmatter JSON,
    tags VARCHAR[],
    aliases VARCHAR[],
    created_date DATE,
    modified_date TIMESTAMP,
    word_count INTEGER
);

-- Links table: graph edges from wikilinks
CREATE TABLE IF NOT EXISTS links (
    link_id INTEGER PRIMARY KEY,
    source_slug VARCHAR NOT NULL,
    target_slug VARCHAR NOT NULL,
    link_text VARCHAR,
    link_type VARCHAR DEFAULT 'wikilink'
);

-- Chunks table: content chunks for RAG retrieval
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id INTEGER PRIMARY KEY,
    note_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    heading_context VARCHAR,
    chunk_type VARCHAR,
    start_line INTEGER,
    end_line INTEGER,
    FOREIGN KEY (note_id) REFERENCES notes(note_id)
);

-- Embeddings table: vector embeddings for semantic search
-- Dimension is configured based on the model used
CREATE TABLE IF NOT EXISTS embeddings (
    embedding_id INTEGER PRIMARY KEY,
    chunk_id INTEGER NOT NULL UNIQUE,
    embedding FLOAT[{embedding_dim}] NOT NULL,
    model_name VARCHAR DEFAULT '{model_name}',
    created_at TIMESTAMP DEFAULT current_timestamp,
    FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
);

-- Hyperedges table: multiway relations (tags, folders, aliases)
-- A hyperedge connects multiple notes via a shared property
CREATE TABLE IF NOT EXISTS hyperedges (
    hyperedge_id INTEGER PRIMARY KEY,
    edge_type VARCHAR NOT NULL,  -- 'tag', 'folder', 'alias'
    edge_value VARCHAR NOT NULL, -- actual tag/folder/alias name
    UNIQUE(edge_type, edge_value)
);

-- Hyperedge membership: which notes belong to which hyperedge
CREATE TABLE IF NOT EXISTS hyperedge_members (
    hyperedge_id INTEGER NOT NULL,
    note_id INTEGER NOT NULL,
    PRIMARY KEY (hyperedge_id, note_id),
    FOREIGN KEY (hyperedge_id) REFERENCES hyperedges(hyperedge_id),
    FOREIGN KEY (note_id) REFERENCES notes(note_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_notes_slug ON notes(slug);
CREATE INDEX IF NOT EXISTS idx_notes_title ON notes(title);
CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_slug);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_slug);
CREATE INDEX IF NOT EXISTS idx_chunks_note ON chunks(note_id);
CREATE INDEX IF NOT EXISTS idx_hyperedge_type ON hyperedges(edge_type);
CREATE INDEX IF NOT EXISTS idx_hyperedge_members_note ON hyperedge_members(note_id);

-- Metadata table to store configuration
CREATE TABLE IF NOT EXISTS metadata (
    key VARCHAR PRIMARY KEY,
    value VARCHAR NOT NULL
);
"""


def init_database(db_path: str, model_name: str = None, embedding_dim: int = None) -> duckdb.DuckDBPyConnection:
    """
    Initialize database with schema and VSS extension.

    Args:
        db_path: Path to DuckDB database file
        model_name: Embedding model name (default: DEFAULT_MODEL)
        embedding_dim: Embedding dimension (auto-detected if not provided)

    Returns:
        Open database connection
    """
    if model_name is None:
        model_name = DEFAULT_MODEL

    if embedding_dim is None:
        embedding_dim = get_embedding_dim(model_name)
        if embedding_dim is None:
            raise ValueError(f"Unknown model '{model_name}'. Please specify --embedding-dim")

    conn = duckdb.connect(db_path)

    # Install and load VSS extension for vector similarity search
    print("Installing VSS extension...")
    conn.execute("INSTALL vss;")
    conn.execute("LOAD vss;")

    # Enable HNSW index persistence for file-based databases
    conn.execute("SET hnsw_enable_experimental_persistence = true;")

    # Create schema with correct embedding dimension
    print(f"Creating schema (model: {model_name}, dim: {embedding_dim})...")
    schema_sql = get_schema_sql(embedding_dim, model_name)
    for statement in schema_sql.strip().split(';'):
        statement = statement.strip()
        if statement:
            conn.execute(statement)

    # Store model info in metadata
    conn.execute("""
        INSERT OR REPLACE INTO metadata (key, value) VALUES
        ('model_name', ?), ('embedding_dim', ?)
    """, [model_name, str(embedding_dim)])

    print("Schema initialized.")
    return conn


def create_hnsw_index(conn: duckdb.DuckDBPyConnection):
    """Create HNSW index for fast cosine similarity search."""
    print("Creating HNSW index on embeddings (this may take a moment)...")
    conn.execute("""
        CREATE INDEX IF NOT EXISTS embedding_cosine_idx
        ON embeddings USING HNSW (embedding)
        WITH (metric = 'cosine')
    """)
    print("HNSW index created.")


def drop_all_tables(conn: duckdb.DuckDBPyConnection):
    """Drop all tables for a clean re-ingestion."""
    print("Dropping existing tables...")
    conn.execute("DROP TABLE IF EXISTS hyperedge_members;")
    conn.execute("DROP TABLE IF EXISTS hyperedges;")
    conn.execute("DROP TABLE IF EXISTS embeddings;")
    conn.execute("DROP TABLE IF EXISTS chunks;")
    conn.execute("DROP TABLE IF EXISTS links;")
    conn.execute("DROP TABLE IF EXISTS notes;")
    print("Tables dropped.")
