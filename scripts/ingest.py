#!/usr/bin/env python3
"""
Ingest Obsidian vault into DuckDB with vector embeddings.

Usage:
    python scripts/ingest.py [vault_path] [--db database.duckdb]

Example:
    python scripts/ingest.py ../SecondBrainCopy_260113
    python scripts/ingest.py ../SecondBrainCopy_260113 --db my_brain.duckdb
"""
import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.ingestion import SecondBrainIngester


def main():
    parser = argparse.ArgumentParser(
        description="Ingest Obsidian vault into DuckDB with vector embeddings"
    )
    parser.add_argument(
        "vault_path",
        nargs="?",
        default="../SecondBrainCopy_260113",
        help="Path to Obsidian vault (default: ../SecondBrainCopy_260113)"
    )
    parser.add_argument(
        "--db",
        default="second_brain.duckdb",
        help="Output database path (default: second_brain.duckdb)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Notes to process per batch (default: 100)"
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=64,
        help="Texts per embedding batch (default: 64, use 128+ for GPU)"
    )

    args = parser.parse_args()

    # Resolve paths
    vault_path = Path(args.vault_path)
    if not vault_path.is_absolute():
        vault_path = Path(__file__).parent.parent / vault_path

    if not vault_path.exists():
        print(f"Error: Vault path does not exist: {vault_path}")
        sys.exit(1)

    db_path = args.db
    if not Path(db_path).is_absolute():
        db_path = str(Path(__file__).parent.parent / db_path)

    print(f"Vault: {vault_path}")
    print(f"Database: {db_path}")
    print()

    ingester = SecondBrainIngester(db_path)
    try:
        ingester.ingest_vault(
            str(vault_path),
            batch_size=args.batch_size,
            embedding_batch_size=args.embedding_batch_size
        )
    finally:
        ingester.close()


if __name__ == "__main__":
    main()
