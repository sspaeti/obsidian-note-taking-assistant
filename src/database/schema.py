"""DuckDB schema initialization with VSS extension."""
import duckdb


SCHEMA_SQL = """
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
-- Using FLOAT[384] for all-MiniLM-L6-v2 model
CREATE TABLE IF NOT EXISTS embeddings (
    embedding_id INTEGER PRIMARY KEY,
    chunk_id INTEGER NOT NULL UNIQUE,
    embedding FLOAT[384] NOT NULL,
    model_name VARCHAR DEFAULT 'all-MiniLM-L6-v2',
    created_at TIMESTAMP DEFAULT current_timestamp,
    FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_notes_slug ON notes(slug);
CREATE INDEX IF NOT EXISTS idx_notes_title ON notes(title);
CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_slug);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_slug);
CREATE INDEX IF NOT EXISTS idx_chunks_note ON chunks(note_id);
"""


def init_database(db_path: str) -> duckdb.DuckDBPyConnection:
    """
    Initialize database with schema and VSS extension.

    Args:
        db_path: Path to DuckDB database file

    Returns:
        Open database connection
    """
    conn = duckdb.connect(db_path)

    # Install and load VSS extension for vector similarity search
    print("Installing VSS extension...")
    conn.execute("INSTALL vss;")
    conn.execute("LOAD vss;")

    # Enable HNSW index persistence for file-based databases
    conn.execute("SET hnsw_enable_experimental_persistence = true;")

    # Create schema
    print("Creating schema...")
    for statement in SCHEMA_SQL.strip().split(';'):
        statement = statement.strip()
        if statement:
            conn.execute(statement)

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
    conn.execute("DROP TABLE IF EXISTS embeddings;")
    conn.execute("DROP TABLE IF EXISTS chunks;")
    conn.execute("DROP TABLE IF EXISTS links;")
    conn.execute("DROP TABLE IF EXISTS notes;")
    print("Tables dropped.")
