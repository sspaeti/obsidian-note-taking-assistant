# Load .env file if it exists
ifneq (,$(wildcard .env))
    include .env
    export
endif

# Defaults (override in .env)
VAULT_PATH ?= /path/to/your/obsidian/vault
DB_PATH ?= second_brain.duckdb

.PHONY: help ingest test-semantic test-backlinks test-connections test-hidden test-sql test-all stats clean

help:
	@echo "Second Brain RAG - Available commands:"
	@echo "  make ingest          - Run full ingestion pipeline"
	@echo "  make test-all        - Run all test queries"
	@echo "  make test-semantic   - Test semantic search"
	@echo "  make test-backlinks  - Test backlinks query"
	@echo "  make test-connections- Test graph connections"
	@echo "  make test-hidden     - Test hidden connections"
	@echo "  make test-sql        - Test raw SQL query"
	@echo "  make stats           - Show database statistics"
	@echo "  make clean           - Remove database file"
	@echo ""
	@echo "Configuration (set in .env):"
	@echo "  VAULT_PATH = $(VAULT_PATH)"
	@echo "  DB_PATH    = $(DB_PATH)"

ingest:
	uv run python scripts/ingest.py "$(VAULT_PATH)"

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

test-all: test-semantic test-backlinks test-connections test-hidden test-sql
	@echo "=== All tests completed ==="

stats:
	@echo "=== Database Statistics ==="
	uv run duckdb "$(DB_PATH)" -c "SELECT 'notes' as table_name, COUNT(*) as count FROM notes UNION ALL SELECT 'links', COUNT(*) FROM links UNION ALL SELECT 'chunks', COUNT(*) FROM chunks UNION ALL SELECT 'embeddings', COUNT(*) FROM embeddings;"

clean:
	rm -f "$(DB_PATH)"
	@echo "Database removed."
