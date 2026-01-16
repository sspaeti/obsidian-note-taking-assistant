"""Bulk ingestion pipeline for Second Brain notes."""
import duckdb
from pathlib import Path
from typing import Generator, List, Dict, Any
import json
from datetime import date, datetime
from tqdm import tqdm

from ..parsers.markdown_parser import parse_note, ParsedNote
from ..parsers.link_extractor import extract_wikilinks
from ..parsers.chunker import chunk_markdown
from ..embeddings.embedder import EmbeddingGenerator
from .schema import init_database, create_hnsw_index, drop_all_tables


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles date and datetime objects."""
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


class SecondBrainIngester:
    """Ingestion pipeline for Obsidian vault into DuckDB."""

    def __init__(self, db_path: str = 'second_brain.duckdb', model_name: str = None):
        """
        Initialize ingester with database connection.

        Args:
            db_path: Path to DuckDB database file
            model_name: Embedding model name (default from schema.DEFAULT_MODEL)
        """
        from .schema import DEFAULT_MODEL
        self.db_path = db_path
        self.model_name = model_name or DEFAULT_MODEL
        self.conn = None
        self.embedder = None

    def _ensure_connection(self):
        """Ensure database connection is open."""
        if self.conn is None:
            self.conn = init_database(self.db_path, self.model_name)

    def _ensure_embedder(self):
        """Ensure embedding model is loaded."""
        if self.embedder is None:
            self.embedder = EmbeddingGenerator(self.model_name)

    def scan_vault(self, vault_path: Path) -> Generator[Path, None, None]:
        """
        Scan vault for markdown files.

        Skips hidden files/folders and non-markdown files.
        """
        for md_file in vault_path.rglob('*.md'):
            # Skip hidden files and folders
            if any(part.startswith('.') for part in md_file.parts):
                continue
            yield md_file

    def ingest_vault(
        self,
        vault_path: str,
        batch_size: int = 100,
        embedding_batch_size: int = 64
    ):
        """
        Main ingestion pipeline.

        1. Parse all markdown files
        2. Extract links
        3. Chunk content
        4. Generate embeddings
        5. Bulk insert into DuckDB

        Args:
            vault_path: Path to Obsidian vault root
            batch_size: Notes to process before database commit
            embedding_batch_size: Texts per embedding batch
        """
        self._ensure_connection()

        vault = Path(vault_path)
        if not vault.exists():
            raise ValueError(f"Vault path does not exist: {vault_path}")

        # Clean start - drop existing tables
        drop_all_tables(self.conn)
        self.conn = init_database(self.db_path, self.model_name)

        files = list(self.scan_vault(vault))
        print(f"Found {len(files)} markdown files")

        notes_data: List[Dict[str, Any]] = []
        links_data: List[Dict[str, Any]] = []
        chunks_data: List[Dict[str, Any]] = []

        note_id = 0
        chunk_id = 0
        link_id = 0
        seen_slugs: Dict[str, int] = {}  # Track slug occurrences for deduplication

        # Phase 1: Parse and extract
        print("\nPhase 1: Parsing notes and extracting links...")
        for file_path in tqdm(files, desc="Parsing"):
            try:
                note = parse_note(file_path, vault)
                note_id += 1

                # Deduplicate slugs by appending counter if needed
                base_slug = note.slug
                if base_slug in seen_slugs:
                    seen_slugs[base_slug] += 1
                    slug = f"{base_slug}-{seen_slugs[base_slug]}"
                else:
                    seen_slugs[base_slug] = 0
                    slug = base_slug

                # Note data - use custom encoder for frontmatter dates
                notes_data.append({
                    'note_id': note_id,
                    'file_path': note.file_path,
                    'slug': slug,
                    'title': note.title,
                    'content': note.content,
                    'frontmatter': json.dumps(note.frontmatter, cls=DateTimeEncoder),
                    'tags': note.tags,
                    'aliases': note.aliases,
                    'created_date': note.created_date,
                    'modified_date': note.modified_date,
                    'word_count': len(note.content.split())
                })

                # Links - use the deduplicated slug as source
                links = extract_wikilinks(note.content, slug)
                for link in links:
                    link_id += 1
                    links_data.append({
                        'link_id': link_id,
                        'source_slug': link.source_slug,
                        'target_slug': link.target_slug,
                        'link_text': link.link_text,
                        'link_type': link.link_type
                    })

                # Chunks
                chunks = chunk_markdown(note.content)
                for i, chunk in enumerate(chunks):
                    chunk_id += 1
                    chunks_data.append({
                        'chunk_id': chunk_id,
                        'note_id': note_id,
                        'chunk_index': i,
                        'content': chunk.content,
                        'heading_context': chunk.heading_context,
                        'chunk_type': chunk.chunk_type,
                        'start_line': chunk.start_line,
                        'end_line': chunk.end_line,
                        'note_title': note.title  # For embedding context
                    })

            except Exception as e:
                print(f"\nError processing {file_path}: {e}")
                continue

        print(f"\nParsed: {len(notes_data)} notes, {len(links_data)} links, {len(chunks_data)} chunks")

        # Phase 2: Generate embeddings
        print("\nPhase 2: Generating embeddings...")
        self._ensure_embedder()

        texts_for_embedding = [
            EmbeddingGenerator.prepare_chunk_for_embedding(
                c['content'],
                c['heading_context'],
                c['note_title']
            )
            for c in chunks_data
        ]

        embeddings = self.embedder.embed_batch(
            texts_for_embedding,
            batch_size=embedding_batch_size
        )

        # Phase 3: Bulk insert with batched commits to avoid transaction overflow
        print("\nPhase 3: Inserting into database...")
        commit_batch_size = 1000  # Commit every 1000 records

        # Insert notes
        print("Inserting notes...")
        self.conn.execute("BEGIN TRANSACTION")
        for i, note in enumerate(tqdm(notes_data, desc="Notes")):
            self.conn.execute("""
                INSERT INTO notes (note_id, file_path, slug, title, content,
                                   frontmatter, tags, aliases, created_date,
                                   modified_date, word_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                note['note_id'], note['file_path'], note['slug'],
                note['title'], note['content'], note['frontmatter'],
                note['tags'], note['aliases'], note['created_date'],
                note['modified_date'], note['word_count']
            ])
            if (i + 1) % commit_batch_size == 0:
                self.conn.execute("COMMIT")
                self.conn.execute("BEGIN TRANSACTION")
        self.conn.execute("COMMIT")

        # Insert links
        print("Inserting links...")
        self.conn.execute("BEGIN TRANSACTION")
        for i, link in enumerate(tqdm(links_data, desc="Links")):
            self.conn.execute("""
                INSERT INTO links (link_id, source_slug, target_slug,
                                   link_text, link_type)
                VALUES (?, ?, ?, ?, ?)
            """, [
                link['link_id'], link['source_slug'], link['target_slug'],
                link['link_text'], link['link_type']
            ])
            if (i + 1) % commit_batch_size == 0:
                self.conn.execute("COMMIT")
                self.conn.execute("BEGIN TRANSACTION")
        self.conn.execute("COMMIT")

        # Insert chunks
        print("Inserting chunks...")
        self.conn.execute("BEGIN TRANSACTION")
        for i, chunk in enumerate(tqdm(chunks_data, desc="Chunks")):
            self.conn.execute("""
                INSERT INTO chunks (chunk_id, note_id, chunk_index, content,
                                    heading_context, chunk_type, start_line, end_line)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                chunk['chunk_id'], chunk['note_id'], chunk['chunk_index'],
                chunk['content'], chunk['heading_context'], chunk['chunk_type'],
                chunk['start_line'], chunk['end_line']
            ])
            if (i + 1) % commit_batch_size == 0:
                self.conn.execute("COMMIT")
                self.conn.execute("BEGIN TRANSACTION")
        self.conn.execute("COMMIT")

        # Insert embeddings
        print("Inserting embeddings...")
        self.conn.execute("BEGIN TRANSACTION")
        for i, emb in enumerate(tqdm(embeddings, desc="Embeddings")):
            self.conn.execute("""
                INSERT INTO embeddings (embedding_id, chunk_id, embedding)
                VALUES (?, ?, ?)
            """, [i + 1, chunks_data[i]['chunk_id'], emb.tolist()])
            if (i + 1) % commit_batch_size == 0:
                self.conn.execute("COMMIT")
                self.conn.execute("BEGIN TRANSACTION")
        self.conn.execute("COMMIT")

        # Build hyperedges from tags and folders
        print("Building hyperedges...")
        hyperedge_map: Dict[tuple, List[int]] = {}  # (type, value) -> [note_ids]

        for note in notes_data:
            note_id = note['note_id']

            # Tag hyperedges
            for tag in note.get('tags', []) or []:
                key = ('tag', tag.lower().strip('#'))
                if key not in hyperedge_map:
                    hyperedge_map[key] = []
                hyperedge_map[key].append(note_id)

            # Folder hyperedge (parent folder path)
            file_path = note.get('file_path', '')
            if '/' in file_path:
                folder = '/'.join(file_path.split('/')[:-1])
                if folder:
                    key = ('folder', folder)
                    if key not in hyperedge_map:
                        hyperedge_map[key] = []
                    hyperedge_map[key].append(note_id)

            # Alias hyperedges
            for alias in note.get('aliases', []) or []:
                key = ('alias', alias.lower())
                if key not in hyperedge_map:
                    hyperedge_map[key] = []
                hyperedge_map[key].append(note_id)

        # Insert hyperedges and members
        print("Inserting hyperedges...")
        hyperedge_id = 0
        self.conn.execute("BEGIN TRANSACTION")
        for (edge_type, edge_value), note_ids in tqdm(hyperedge_map.items(), desc="Hyperedges"):
            hyperedge_id += 1
            self.conn.execute("""
                INSERT INTO hyperedges (hyperedge_id, edge_type, edge_value)
                VALUES (?, ?, ?)
            """, [hyperedge_id, edge_type, edge_value])

            for nid in note_ids:
                self.conn.execute("""
                    INSERT INTO hyperedge_members (hyperedge_id, note_id)
                    VALUES (?, ?)
                """, [hyperedge_id, nid])

            if hyperedge_id % commit_batch_size == 0:
                self.conn.execute("COMMIT")
                self.conn.execute("BEGIN TRANSACTION")
        self.conn.execute("COMMIT")

        # Create HNSW index
        print("\nPhase 4: Creating search index...")
        create_hnsw_index(self.conn)

        # Summary
        hyperedge_member_count = sum(len(nids) for nids in hyperedge_map.values())
        print("\n" + "=" * 50)
        print("Ingestion Complete!")
        print("=" * 50)
        print(f"Notes:       {len(notes_data):,}")
        print(f"Links:       {len(links_data):,}")
        print(f"Chunks:      {len(chunks_data):,}")
        print(f"Embeddings:  {len(embeddings):,}")
        print(f"Hyperedges:  {len(hyperedge_map):,} ({hyperedge_member_count:,} memberships)")
        print(f"Database:    {self.db_path}")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
