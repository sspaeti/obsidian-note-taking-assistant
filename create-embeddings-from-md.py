import duckdb
import frontmatter
import re
from pathlib import Path
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict
import pyarrow as pa

def setup_database():
    """Initialize DuckDB database with necessary tables"""
    print("Setting up database...")
    conn = duckdb.connect("notes.duckdb")
    
    # Create tables for notes and their embeddings
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id VARCHAR PRIMARY KEY,
            title VARCHAR,
            content TEXT,
            headers TEXT[],
            links TEXT[],
            tags TEXT[],
            created_date DATE,
            outgoing TEXT[]
        );
    """)
    print("Created notes table")
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS note_chunks (
            chunk_id VARCHAR PRIMARY KEY,
            note_id VARCHAR,
            chunk_type VARCHAR,  -- 'header', 'paragraph', 'full'
            chunk_text TEXT,
            embedding FLOAT[768]  -- Changed dimension for 'all-MiniLM-L6-v2'
        );
    """)
    print("Created note_chunks table")
    
    return conn

def parse_markdown(file_path: str) -> Dict:
    """Parse a markdown file into structured components"""
    content = Path(file_path).read_text(encoding='utf-8')
    
    # Parse frontmatter
    post = frontmatter.loads(content)
    
    # Extract headers
    headers = re.findall(r'^#{1,3}\s+(.+)$', content, re.MULTILINE)
    
    # Extract wiki-style links
    links = re.findall(r'\[\[(.*?)\]\]', content)
    
    # Extract tags
    tags = re.findall(r'#([\w/🌻🗃]+)', content)
    
    return {
        'id': str(file_path),
        'title': headers[0] if headers else Path(file_path).stem,
        'content': post.content,
        'headers': headers,
        'links': links,
        'tags': tags,
        'created_date': post.get('Created', None),
        'outgoing': post.get('Outgoing', [])
    }

def chunk_content(note: Dict) -> List[Dict]:
    """Split note content into meaningful chunks"""
    chunks = []
    
    # Add full document chunk
    chunks.append({
        'chunk_id': f"{note['id']}_full",
        'note_id': note['id'],
        'chunk_type': 'full',
        'chunk_text': note['content']
    })
    
    # Split by headers
    sections = re.split(r'^#{1,3}\s+', note['content'], flags=re.MULTILINE)
    for i, section in enumerate(sections[1:], 1):  # Skip first empty split
        chunks.append({
            'chunk_id': f"{note['id']}_section_{i}",
            'note_id': note['id'],
            'chunk_type': 'section',
            'chunk_text': section.strip()
        })
    
    return chunks

def setup_embedding_model():
    """Initialize the sentence transformer model"""
    print("Loading embedding model...")
    # Using a smaller, efficient model
    return SentenceTransformer('all-MiniLM-L6-v2')

def process_notes(folder_path: str, conn: duckdb.DuckDBPyConnection, model):
    """Process all markdown files in a folder"""
    print(f"Processing markdown files from {folder_path}...")
    
    # Convert string to Path if necessary
    folder_path = Path(folder_path)
    
    # Check if directory exists
    if not folder_path.exists():
        raise ValueError(f"Directory not found: {folder_path}")
        
    files = list(folder_path.glob('**/*.md'))
    print(f"Found {len(files)} markdown files")
    
    for i, file_path in enumerate(files, 1):
        print(f"Processing file {i}/{len(files)}: {file_path.name}")
        # Parse and store note
        note = parse_markdown(str(file_path))
        conn.execute("""
            INSERT OR REPLACE INTO notes 
            (id, title, content, headers, links, tags, created_date, outgoing)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [note['id'], note['title'], note['content'], note['headers'], 
              note['links'], note['tags'], note['created_date'], note['outgoing']])
        
        # Create and store chunks with embeddings
        chunks = chunk_content(note)
        for chunk in chunks:
            embedding = model.encode(chunk['chunk_text'], normalize_embeddings=True)
            conn.execute("""
                INSERT OR REPLACE INTO note_chunks 
                (chunk_id, note_id, chunk_type, chunk_text, embedding)
                VALUES (?, ?, ?, ?, ?)
            """, [chunk['chunk_id'], chunk['note_id'], 
                  chunk['chunk_type'], chunk['chunk_text'], embedding])

def setup_search(conn: duckdb.DuckDBPyConnection):
    """Set up vector search capabilities"""
    print("Setting up vector search capabilities...")
    conn.execute("INSTALL vss;")
    conn.execute("LOAD vss;")
    conn.execute("SET GLOBAL hnsw_enable_experimental_persistence = true;")
    conn.execute("""
        CREATE INDEX IF NOT EXISTS embedding_idx ON note_chunks 
        USING HNSW (embedding) WITH (metric = 'cosine');
    """)
    print("Vector search index created")

def search_notes(query: str, conn: duckdb.DuckDBPyConnection, model, limit: int = 5):
    """Search notes using vector similarity"""
    print(f"Searching for: {query}")
    query_embedding = model.encode(query, normalize_embeddings=True)
    
    results = conn.execute("""
        WITH top_chunks AS (
            FROM note_chunks
            SELECT chunk_id, note_id, chunk_type, chunk_text,
                   1 - (1 - array_inner_product(embedding, ?)) / 2 as similarity
            ORDER BY similarity DESC
            LIMIT ?
        )
        SELECT n.title, n.tags, c.chunk_text, c.similarity
        FROM top_chunks c
        JOIN notes n ON c.note_id = n.id
        ORDER BY c.similarity DESC
    """, [query_embedding, limit]).fetchdf()
    
    return results

if __name__ == "__main__":
    # Initialize database and model
    conn = setup_database()
    model = setup_embedding_model()
    
    # Path to your Obsidian vault
    vault_path = "data/books/"  # Replace this with your actual vault path
    
    try:
        # Process all markdown files
        process_notes(vault_path, conn, model)
        
        # Set up search capabilities
        setup_search(conn)
        
        # Example searches
        print("\nTesting searches:")
        print("\nInvestment frameworks:")
        print(search_notes("investment frameworks", conn, model))
        
        print("\nSecond brain related:")
        print(search_notes("second brain methodology", conn, model))
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("\nClosing database connection...")
        conn.close()
