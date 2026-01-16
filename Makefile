# Load .env file if it exists
ifneq (,$(wildcard .env))
    include .env
    export
endif

# Defaults (override in .env or command line)
VAULT_PATH ?= /path/to/your/obsidian/vault
DB_PATH ?= second_brain.duckdb
MODEL ?= all-MiniLM-L6-v2

.PHONY: help ingest test-semantic test-backlinks test-connections test-hidden test-shared-tags test-graph-boosted test-sql test-all stats clean

help:
	@echo "Second Brain RAG - Available commands:"
	@echo "  make ingest           - Run full ingestion pipeline"
	@echo "  make test-all         - Run all test queries"
	@echo "  make test-semantic    - Test semantic search"
	@echo "  make test-backlinks   - Test backlinks query"
	@echo "  make test-connections - Test graph connections"
	@echo "  make test-hidden      - Test hidden connections"
	@echo "  make test-shared-tags - Test shared tags (hyperedge)"
	@echo "  make test-graph-boosted - Test graph-boosted search"
	@echo "  make test-sql         - Test raw SQL query"
	@echo "  make stats            - Show database statistics"
	@echo "  make clean            - Remove database file"
	@echo ""
	@echo "Configuration (set in .env or via command line):"
	@echo "  VAULT_PATH = $(VAULT_PATH)"
	@echo "  DB_PATH    = $(DB_PATH)"
	@echo "  MODEL      = $(MODEL)"
	@echo ""
	@echo "Models: all-MiniLM-L6-v2 (fast), BAAI/bge-m3 (quality)"

ingest:
	uv run python scripts/ingest.py "$(VAULT_PATH)" --model "$(MODEL)"

test-semantic:
	@echo "=== Semantic Search: 'semantic layer data modeling' ==="
	uv run python scripts/query.py semantic "semantic layer data modeling" --limit 5

test-backlinks:
	@echo "=== Backlinks to 'functional-data-engineering' ==="
	uv run python scripts/query.py backlinks "functional-data-engineering"

test-connections:
	@echo "=== Connections from 'resources/-zettelkasten/-zettelkasten/data-contracts/data-contracts' (2 hops) ==="
	uv run python scripts/query.py connections "resources/-zettelkasten/-zettelkasten/data-contracts/data-contracts" --hops 2

test-hidden:
	@echo "=== Hidden connections: 'Python pipelines' from 'functional-data-engineering' ==="
	uv run python scripts/query.py hidden "Python pipelines" --seed "functional-data-engineering" --limit 5

test-sql:
	@echo "=== Most connected notes (hub notes) ==="
	uv run python scripts/query.py sql "SELECT n.title, n.slug, COUNT(DISTINCT lo.target_slug) + COUNT(DISTINCT li.source_slug) as connections FROM notes n LEFT JOIN links lo ON lo.source_slug = n.slug LEFT JOIN links li ON li.target_slug = n.slug GROUP BY n.title, n.slug ORDER BY connections DESC LIMIT 10"

test-shared-tags:
	@echo "=== Notes sharing tags with 'python' ==="
	uv run python scripts/query.py shared-tags "python" --min-shared 2 --limit 10

test-graph-boosted:
	@echo "=== Graph-boosted search: 'data modeling' from 'data-contracts' ==="
	uv run python scripts/query.py graph-boosted "data modeling" --seed "data-contracts" --limit 10

test-all: test-semantic test-backlinks test-connections test-hidden test-shared-tags test-graph-boosted test-sql
	@echo "=== All tests completed ==="

stats:
	@echo "=== Database Statistics ==="
	uv run duckdb "$(DB_PATH)" -c "SELECT 'notes' as table_name, COUNT(*) as count FROM notes UNION ALL SELECT 'links', COUNT(*) FROM links UNION ALL SELECT 'chunks', COUNT(*) FROM chunks UNION ALL SELECT 'embeddings', COUNT(*) FROM embeddings UNION ALL SELECT 'hyperedges', COUNT(*) FROM hyperedges UNION ALL SELECT 'hyperedge_members', COUNT(*) FROM hyperedge_members;"

clean:
	rm -f "$(DB_PATH)"
	@echo "Database removed."
