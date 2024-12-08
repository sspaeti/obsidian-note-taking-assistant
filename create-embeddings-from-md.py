import duckdb
import frontmatter
import re
from pathlib import Path
from FlagEmbedding import BGEM3FlagModel
import torch
import numpy as np
from typing import List, Dict
import pyarrow as pa

def setup_database():
    """Initialize DuckDB database with necessary tables"""
    conn = duckdb.connect("notes.db")
    
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
            references TEXT[]
        );
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS note_chunks (
            chunk_id VARCHAR PRIMARY KEY,
            note_id VARCHAR,
            chunk_type VARCHAR,  -- 'header', 'paragraph', 'full'
            chunk_text TEXT,
            embedding FLOAT[1024]
        );
    """)
    
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
        'references': post.get('References', [])
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
    """Initialize the BGE-M3 embedding model"""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return BGEM3FlagModel('BAAI/bge-m3', use_fp16=True, device=device)

def process_notes(folder_path: str, conn: duckdb.DuckDBPyConnection, model):
    """Process all markdown files in a folder"""
    for file_path in Path(folder_path).glob('**/*.md'):
        # Parse and store note
        note = parse_markdown(str(file_path))
        conn.execute("""
            INSERT INTO notes 
            (id, title, content, headers, links, tags, created_date, references)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [note['id'], note['title'], note['content'], note['headers'], 
              note['links'], note['tags'], note['created_date'], note['references']])
        
        # Create and store chunks with embeddings
        chunks = chunk_content(note)
        for chunk in chunks:
            embedding = model.encode(chunk['chunk_text'])['dense_vecs'].astype(np.float32)
            conn.execute("""
                INSERT INTO note_chunks 
                (chunk_id, note_id, chunk_type, chunk_text, embedding)
                VALUES (?, ?, ?, ?, ?)
            """, [chunk['chunk_id'], chunk['note_id'], 
                  chunk['chunk_type'], chunk['chunk_text'], embedding[0]])

def setup_search(conn: duckdb.DuckDBPyConnection):
    """Set up vector search capabilities"""
    conn.execute("INSTALL vss;")
    conn.execute("LOAD vss;")
    conn.execute("SET GLOBAL hnsw_enable_experimental_persistence = true;")
    conn.execute("""
        CREATE INDEX embedding_idx ON note_chunks 
        USING HNSW (embedding) WITH (metric = 'ip');
    """)

def search_notes(query: str, conn: duckdb.DuckDBPyConnection, model, limit: int = 5):
    """Search notes using vector similarity"""
    query_embedding = model.encode(query)['dense_vecs'].astype(np.float32)
    
    results = conn.execute("""
        WITH top_chunks AS (
            FROM note_chunks
            SELECT chunk_id, note_id, chunk_type, chunk_text,
                   array_inner_product(embedding, ?) as similarity
            ORDER BY similarity DESC
            LIMIT ?
        )
        SELECT n.title, n.tags, c.chunk_text, c.similarity
        FROM top_chunks c
        JOIN notes n ON c.note_id = n.id
        ORDER BY c.similarity DESC
    """, [query_embedding[0], limit]).fetchdf()
    
    return results

# Usage example:
def main():
    conn = setup_database()
    model = setup_embedding_model()
    
    # Process all markdown files
    process_notes("data/", conn, model)
    
    # Set up search capabilities
    setup_search(conn)
    
    # Example searches
    print("Investment frameworks:")
    print(search_notes("investment frameworks", conn, model))
    
    print("\nSecond brain related:")
    print(search_notes("second brain methodology", conn, model))
