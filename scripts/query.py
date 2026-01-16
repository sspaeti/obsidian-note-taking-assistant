#!/usr/bin/env python3
"""
Query Second Brain knowledge base.

Usage:
    python scripts/query.py semantic "search query" [--limit N]
    python scripts/query.py backlinks "note-slug"
    python scripts/query.py connections "note-slug" [--hops N]
    python scripts/query.py hidden "query" --seed "note-slug"
    python scripts/query.py shared-tags "note-slug" [--min-shared N]
    python scripts/query.py graph-boosted "query" --seed "note-slug" [--boost N]
    python scripts/query.py sql "SELECT * FROM notes LIMIT 5"

Examples:
    python scripts/query.py semantic "semantic layer data modeling" --limit 10
    python scripts/query.py backlinks "functional-data-engineering"
    python scripts/query.py connections "data-contracts" --hops 2
    python scripts/query.py hidden "Python pipelines" --seed "functional-data-engineering"
    python scripts/query.py shared-tags "data-contracts" --min-shared 2
    python scripts/query.py graph-boosted "data modeling" --seed "data-contracts" --boost 1.3
"""
import argparse
import sys
from pathlib import Path
from typing import Optional, List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import duckdb
from sentence_transformers import SentenceTransformer


class SecondBrainQuery:
    """Query interface for Second Brain knowledge base."""

    def __init__(self, db_path: str = 'second_brain.duckdb'):
        """Initialize with database connection."""
        self.db_path = db_path
        self.conn = duckdb.connect(db_path, read_only=True)
        self.conn.execute("LOAD vss;")
        self._embedder = None

        # Read model config from database metadata
        try:
            result = self.conn.execute(
                "SELECT value FROM metadata WHERE key = 'model_name'"
            ).fetchone()
            self.model_name = result[0] if result else 'all-MiniLM-L6-v2'

            result = self.conn.execute(
                "SELECT value FROM metadata WHERE key = 'embedding_dim'"
            ).fetchone()
            self.embedding_dim = int(result[0]) if result else 384
        except Exception:
            # Fallback for old databases without metadata table
            self.model_name = 'all-MiniLM-L6-v2'
            self.embedding_dim = 384

    @property
    def embedder(self):
        """Lazy load embedding model."""
        if self._embedder is None:
            print(f"Loading embedding model: {self.model_name}...", file=sys.stderr)
            self._embedder = SentenceTransformer(self.model_name)
        return self._embedder

    def semantic_search(
        self,
        query: str,
        limit: int = 10,
        tags: Optional[List[str]] = None
    ) -> List[dict]:
        """
        Search notes by semantic similarity.

        Args:
            query: Natural language search query
            limit: Maximum results
            tags: Optional tag filter

        Returns:
            List of matching notes with similarity scores
        """
        query_embedding = self.embedder.encode(query).tolist()

        sql = f"""
            SELECT DISTINCT
                n.title,
                n.slug,
                n.file_path,
                c.content,
                c.heading_context,
                1 - array_cosine_distance(e.embedding, $1::FLOAT[{self.embedding_dim}]) as similarity
            FROM embeddings e
            JOIN chunks c ON c.chunk_id = e.chunk_id
            JOIN notes n ON n.note_id = c.note_id
        """

        if tags:
            tag_filters = " OR ".join([f"list_contains(n.tags, '{t}')" for t in tags])
            sql += f" WHERE ({tag_filters})"

        sql += " ORDER BY similarity DESC LIMIT $2"

        results = self.conn.execute(sql, [query_embedding, limit]).fetchall()

        return [
            {
                'title': r[0],
                'slug': r[1],
                'file_path': r[2],
                'snippet': r[3][:300] + "..." if len(r[3]) > 300 else r[3],
                'heading': r[4],
                'similarity': round(r[5], 4)
            }
            for r in results
        ]

    def find_backlinks(self, slug: str) -> List[dict]:
        """
        Find all notes that link TO the specified note.

        Args:
            slug: Target note slug

        Returns:
            List of notes linking to this note
        """
        sql = """
            SELECT DISTINCT
                n.title,
                n.slug,
                l.link_text,
                l.link_type
            FROM links l
            JOIN notes n ON n.slug = l.source_slug
            WHERE l.target_slug = $1
            ORDER BY n.title
        """

        results = self.conn.execute(sql, [slug]).fetchall()

        return [
            {
                'title': r[0],
                'slug': r[1],
                'link_text': r[2],
                'link_type': r[3]
            }
            for r in results
        ]

    def find_connections(self, slug: str, hops: int = 2) -> dict:
        """
        Find notes connected via backlinks within N hops.

        Args:
            slug: Starting note slug
            hops: Maximum link distance (1-3)

        Returns:
            Dict with notes organized by hop distance
        """
        hops = min(max(hops, 1), 3)

        sql = """
            WITH RECURSIVE connected(slug, hop, path) AS (
                SELECT target_slug, 1, ARRAY[source_slug, target_slug]
                FROM links WHERE source_slug = $1

                UNION

                SELECT l.target_slug, c.hop + 1, list_append(c.path, l.target_slug)
                FROM connected c
                JOIN links l ON l.source_slug = c.slug
                WHERE c.hop < $2
                  AND NOT list_contains(c.path, l.target_slug)
            )
            SELECT DISTINCT n.title, c.slug, c.hop
            FROM connected c
            JOIN notes n ON n.slug = c.slug
            WHERE c.slug != $1
            ORDER BY c.hop, n.title
        """

        results = self.conn.execute(sql, [slug, hops]).fetchall()

        connections = {}
        for title, connected_slug, hop in results:
            hop_key = f"hop_{hop}"
            if hop_key not in connections:
                connections[hop_key] = []
            connections[hop_key].append({
                'title': title,
                'slug': connected_slug
            })

        return connections

    def find_hidden_connections(
        self,
        query: str,
        seed_slug: str,
        limit: int = 10
    ) -> List[dict]:
        """
        Find semantically similar notes NOT directly linked to seed.

        These represent potentially valuable non-obvious connections.

        Args:
            query: Search query for semantic similarity
            seed_slug: Note to check link distance from
            limit: Maximum results

        Returns:
            List of unlinked but semantically related notes
        """
        query_embedding = self.embedder.encode(query).tolist()

        sql = f"""
            WITH semantic_similar AS (
                SELECT DISTINCT
                    n.slug,
                    n.title,
                    c.content,
                    MIN(1 - array_cosine_distance(e.embedding, $1::FLOAT[{self.embedding_dim}])) as similarity
                FROM embeddings e
                JOIN chunks c ON c.chunk_id = e.chunk_id
                JOIN notes n ON n.note_id = c.note_id
                GROUP BY n.slug, n.title, c.content
                HAVING MIN(array_cosine_distance(e.embedding, $1::FLOAT[{self.embedding_dim}])) < 0.6
            ),
            direct_links AS (
                SELECT DISTINCT target_slug as slug FROM links WHERE source_slug = $2
                UNION
                SELECT DISTINCT source_slug as slug FROM links WHERE target_slug = $2
            )
            SELECT
                ss.title,
                ss.slug,
                ss.content,
                ss.similarity
            FROM semantic_similar ss
            LEFT JOIN direct_links dl ON ss.slug = dl.slug
            WHERE dl.slug IS NULL AND ss.slug != $2
            ORDER BY ss.similarity DESC
            LIMIT $3
        """

        results = self.conn.execute(sql, [query_embedding, seed_slug, limit]).fetchall()

        return [
            {
                'title': r[0],
                'slug': r[1],
                'snippet': r[2][:300] + "..." if len(r[2]) > 300 else r[2],
                'similarity': round(r[3], 4)
            }
            for r in results
        ]

    def find_shared_tags(
        self,
        slug: str,
        min_shared: int = 2,
        limit: int = 20
    ) -> List[dict]:
        """
        Find notes sharing multiple tags via hyperedges.

        Args:
            slug: Note slug to find related notes for
            min_shared: Minimum number of shared tags
            limit: Maximum results

        Returns:
            List of notes sharing tags with the specified note
        """
        sql = """
            WITH seed_hyperedges AS (
                SELECT hm.hyperedge_id
                FROM hyperedge_members hm
                JOIN notes n ON n.note_id = hm.note_id
                JOIN hyperedges h ON h.hyperedge_id = hm.hyperedge_id
                WHERE n.slug = $1 AND h.edge_type = 'tag'
            )
            SELECT n.title, n.slug, COUNT(*) as shared_count,
                   list(h.edge_value) as shared_tags
            FROM hyperedge_members hm
            JOIN notes n ON n.note_id = hm.note_id
            JOIN hyperedges h ON h.hyperedge_id = hm.hyperedge_id
            WHERE hm.hyperedge_id IN (SELECT hyperedge_id FROM seed_hyperedges)
              AND n.slug != $1
              AND h.edge_type = 'tag'
            GROUP BY n.title, n.slug
            HAVING COUNT(*) >= $2
            ORDER BY shared_count DESC
            LIMIT $3
        """

        results = self.conn.execute(sql, [slug, min_shared, limit]).fetchall()

        return [
            {
                'title': r[0],
                'slug': r[1],
                'shared_count': r[2],
                'shared_tags': r[3]
            }
            for r in results
        ]

    def graph_boosted_search(
        self,
        query: str,
        seed_slug: str,
        limit: int = 10,
        boost_factor: float = 1.2
    ) -> List[dict]:
        """
        Semantic search with graph connectivity boost.

        Notes that are both semantically similar AND connected via links
        get a score boost.

        Args:
            query: Search query
            seed_slug: Note to check graph connectivity from
            limit: Maximum results
            boost_factor: Multiplier for graph-connected results

        Returns:
            List of notes with combined semantic + graph scores
        """
        query_embedding = self.embedder.encode(query).tolist()

        sql = f"""
            WITH semantic_matches AS (
                SELECT DISTINCT ON (n.slug)
                    n.slug,
                    n.title,
                    c.content,
                    c.heading_context,
                    1 - array_cosine_distance(e.embedding, $1::FLOAT[{self.embedding_dim}]) as similarity
                FROM embeddings e
                JOIN chunks c ON c.chunk_id = e.chunk_id
                JOIN notes n ON n.note_id = c.note_id
                ORDER BY n.slug, similarity DESC
            ),
            graph_connected AS (
                SELECT DISTINCT target_slug as slug FROM links WHERE source_slug = $2
                UNION
                SELECT DISTINCT source_slug as slug FROM links WHERE target_slug = $2
            )
            SELECT
                sm.title,
                sm.slug,
                sm.content,
                sm.heading_context,
                sm.similarity,
                CASE WHEN gc.slug IS NOT NULL THEN true ELSE false END as is_linked,
                sm.similarity * CASE WHEN gc.slug IS NOT NULL THEN $3 ELSE 1.0 END as final_score
            FROM semantic_matches sm
            LEFT JOIN graph_connected gc ON gc.slug = sm.slug
            WHERE sm.slug != $2
            ORDER BY final_score DESC
            LIMIT $4
        """

        results = self.conn.execute(sql, [query_embedding, seed_slug, boost_factor, limit]).fetchall()

        return [
            {
                'title': r[0],
                'slug': r[1],
                'snippet': r[2][:300] + "..." if len(r[2]) > 300 else r[2],
                'heading': r[3],
                'similarity': round(r[4], 4),
                'is_linked': r[5],
                'final_score': round(r[6], 4)
            }
            for r in results
        ]

    def execute_sql(self, query: str) -> str:
        """Execute raw SQL query (read-only)."""
        query_lower = query.strip().lower()
        if not (query_lower.startswith('select') or query_lower.startswith('with')):
            return "Error: Only SELECT queries are allowed."

        try:
            result = self.conn.execute(query).fetchdf()
            return result.to_markdown(index=False)
        except Exception as e:
            return f"Query error: {str(e)}"

    def close(self):
        """Close database connection."""
        self.conn.close()


def format_semantic_results(results: List[dict]) -> str:
    """Format semantic search results for display."""
    if not results:
        return "No results found."

    output = []
    for r in results:
        heading = f" ({r['heading']})" if r['heading'] else ""
        output.append(f"\n## {r['title']}{heading}")
        output.append(f"**Slug:** {r['slug']} | **Similarity:** {r['similarity']}")
        output.append(f"\n{r['snippet']}")
        output.append("-" * 60)

    return "\n".join(output)


def format_backlinks(results: List[dict], slug: str) -> str:
    """Format backlink results for display."""
    if not results:
        return f"No backlinks found for '{slug}'"

    output = [f"# Backlinks to '{slug}'\n"]
    for r in results:
        output.append(f"- **{r['title']}** ({r['slug']}) - linked as: \"{r['link_text']}\"")

    return "\n".join(output)


def format_connections(connections: dict, slug: str, hops: int) -> str:
    """Format connection results for display."""
    if not connections:
        return f"No connections found from '{slug}'"

    output = [f"# Connections from '{slug}' (up to {hops} hops)\n"]

    for hop_key in sorted(connections.keys()):
        hop_num = int(hop_key.split('_')[1])
        output.append(f"\n## {hop_num} hop{'s' if hop_num > 1 else ''} away:")
        for note in connections[hop_key]:
            output.append(f"- {note['title']} ({note['slug']})")

    return "\n".join(output)


def format_hidden(results: List[dict], query: str, seed: str) -> str:
    """Format hidden connection results for display."""
    if not results:
        return f"No hidden connections found for '{query}' (seed: {seed})"

    output = [f"# Hidden Connections"]
    output.append(f"Notes similar to '{query}' but NOT linked to '{seed}':\n")

    for r in results:
        output.append(f"\n## {r['title']}")
        output.append(f"**Slug:** {r['slug']} | **Similarity:** {r['similarity']}")
        output.append(f"\n{r['snippet']}")
        output.append("-" * 60)

    return "\n".join(output)


def format_shared_tags(results: List[dict], slug: str, min_shared: int) -> str:
    """Format shared tags results for display."""
    if not results:
        return f"No notes found sharing {min_shared}+ tags with '{slug}'"

    output = [f"# Notes Sharing Tags with '{slug}' (min: {min_shared})\n"]

    for r in results:
        tags_str = ", ".join(r['shared_tags'][:5])
        if len(r['shared_tags']) > 5:
            tags_str += f" (+{len(r['shared_tags']) - 5} more)"
        output.append(f"- **{r['title']}** ({r['slug']})")
        output.append(f"  Shared: {r['shared_count']} tags - {tags_str}")

    return "\n".join(output)


def format_graph_boosted(results: List[dict], query: str, seed: str) -> str:
    """Format graph-boosted search results for display."""
    if not results:
        return f"No results found for '{query}'"

    output = [f"# Graph-Boosted Search: '{query}'"]
    output.append(f"Results boosted by link proximity to '{seed}':\n")

    for r in results:
        link_indicator = " [LINKED]" if r['is_linked'] else ""
        heading = f" ({r['heading']})" if r['heading'] else ""
        output.append(f"\n## {r['title']}{heading}{link_indicator}")
        output.append(f"**Slug:** {r['slug']} | **Similarity:** {r['similarity']} | **Final:** {r['final_score']}")
        output.append(f"\n{r['snippet']}")
        output.append("-" * 60)

    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser(
        description="Query Second Brain knowledge base",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/query.py semantic "semantic layer data modeling"
    python scripts/query.py backlinks "functional-data-engineering"
    python scripts/query.py connections "data-contracts" --hops 2
    python scripts/query.py hidden "Python pipelines" --seed "functional-data-engineering"
    python scripts/query.py shared-tags "data-contracts" --min-shared 2
    python scripts/query.py graph-boosted "data modeling" --seed "data-contracts"
    python scripts/query.py sql "SELECT title, slug FROM notes LIMIT 10"
        """
    )
    parser.add_argument(
        "command",
        choices=["semantic", "backlinks", "connections", "hidden", "shared-tags", "graph-boosted", "sql"],
        help="Query type"
    )
    parser.add_argument(
        "query",
        help="Search query or note slug"
    )
    parser.add_argument(
        "--db",
        default="second_brain.duckdb",
        help="Database path (default: second_brain.duckdb)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum results (default: 10)"
    )
    parser.add_argument(
        "--hops",
        type=int,
        default=2,
        help="Connection hops for 'connections' command (default: 2)"
    )
    parser.add_argument(
        "--seed",
        help="Seed slug for 'hidden' command"
    )
    parser.add_argument(
        "--tags",
        help="Comma-separated tags to filter (for semantic search)"
    )
    parser.add_argument(
        "--min-shared",
        type=int,
        default=2,
        help="Minimum shared tags for 'shared-tags' command (default: 2)"
    )
    parser.add_argument(
        "--boost",
        type=float,
        default=1.2,
        help="Boost factor for linked notes in 'graph-boosted' command (default: 1.2)"
    )

    args = parser.parse_args()

    # Resolve database path
    db_path = args.db
    if not Path(db_path).is_absolute():
        db_path = str(Path(__file__).parent.parent / db_path)

    if not Path(db_path).exists():
        print(f"Error: Database not found: {db_path}")
        print("Run 'python scripts/ingest.py' first to create the database.")
        sys.exit(1)

    qb = SecondBrainQuery(db_path)

    try:
        if args.command == "semantic":
            tags = args.tags.split(',') if args.tags else None
            results = qb.semantic_search(args.query, limit=args.limit, tags=tags)
            print(format_semantic_results(results))

        elif args.command == "backlinks":
            results = qb.find_backlinks(args.query)
            print(format_backlinks(results, args.query))

        elif args.command == "connections":
            results = qb.find_connections(args.query, hops=args.hops)
            print(format_connections(results, args.query, args.hops))

        elif args.command == "hidden":
            if not args.seed:
                print("Error: --seed is required for 'hidden' command")
                sys.exit(1)
            results = qb.find_hidden_connections(args.query, args.seed, limit=args.limit)
            print(format_hidden(results, args.query, args.seed))

        elif args.command == "shared-tags":
            results = qb.find_shared_tags(args.query, min_shared=args.min_shared, limit=args.limit)
            print(format_shared_tags(results, args.query, args.min_shared))

        elif args.command == "graph-boosted":
            if not args.seed:
                print("Error: --seed is required for 'graph-boosted' command")
                sys.exit(1)
            results = qb.graph_boosted_search(args.query, args.seed, limit=args.limit, boost_factor=args.boost)
            print(format_graph_boosted(results, args.query, args.seed))

        elif args.command == "sql":
            result = qb.execute_sql(args.query)
            print(result)

    finally:
        qb.close()


if __name__ == "__main__":
    main()
