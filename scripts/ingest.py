#!/usr/bin/env python3
"""
Ingest Obsidian vault into DuckDB with vector embeddings.

Usage:
    python scripts/ingest.py <vault_path> [--db database.duckdb] [--model MODEL]

Example:
    python scripts/ingest.py /path/to/obsidian/vault
    python scripts/ingest.py ~/Documents/MyVault --db my_brain.duckdb
    python scripts/ingest.py ~/Documents/MyVault --model BAAI/bge-m3  # Higher quality, slower
    python scripts/ingest.py ~/Documents/MyVault --model all-MiniLM-L6-v2  # Fast default
"""
import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.ingestion import SecondBrainIngester
from src.database.schema import MODEL_CONFIGS, DEFAULT_MODEL


def main():
    available_models = ", ".join(MODEL_CONFIGS.keys())

    parser = argparse.ArgumentParser(
        description="Ingest Obsidian vault into DuckDB with vector embeddings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Available models (or use any sentence-transformers model):
  {available_models}

Default: {DEFAULT_MODEL}
        """
    )
    parser.add_argument(
        "vault_path",
        help="Path to Obsidian vault"
    )
    parser.add_argument(
        "--db",
        default="second_brain.duckdb",
        help="Output database path (default: second_brain.duckdb)"
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Embedding model (default: {DEFAULT_MODEL})"
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
    print(f"Model: {args.model}")
    print()

    ingester = SecondBrainIngester(db_path, model_name=args.model)
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
