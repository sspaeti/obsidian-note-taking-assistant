# Load .env file if it exists
ifneq (,$(wildcard .env))
    include .env
    export
endif

# Defaults (override in .env or command line)
VAULT_PATH ?= /path/to/your/obsidian/vault
DB_PATH ?= second_brain.duckdb
# MODEL ?= all-MiniLM-L6-v2
MODEL ?= BAAI/bge-m3

.PHONY: help ingest test-semantic test-backlinks test-connections test-hidden test-shared-tags test-graph-boosted test-sql test-all stats clean embed-server web-install web-dev web-build web-start web-lint web-deploy

help:
	@echo "Second Brain RAG - Available commands:"
	@echo ""
	@echo "Ingestion & Testing:"
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
	@echo "  make embed-server     - Start local embedding server (port 8001)"
	@echo ""
	@echo "Web App (in web-app/):"
	@echo "  make web-install      - Install npm dependencies"
	@echo "  make web-dev          - Start development server (http://localhost:3000)"
	@echo "  make web-build        - Build for production"
	@echo "  make web-start        - Start production server"
	@echo "  make web-lint         - Run ESLint"
	@echo "  make web-deploy       - Deploy to Vercel"
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

embed-server:
	@echo "Starting local embedding server on http://localhost:8001"
	uv run uvicorn api.embed_server:app --host 0.0.0.0 --port 8001

# Web App commands
web-install:
	cd web-app && npm install

web-dev:
	@echo "Starting dev server at http://localhost:3000"
	@(sleep 2 && xdg-open http://localhost:3000) &
	cd web-app && npm run dev

web-build:
	cd web-app && npm run build

web-start:
	cd web-app && npm run start

web-lint:
	cd web-app && npm run lint

web-deploy:
	cd web-app && npx vercel
	cd web-app && npx vercel

web-redeploy-prod:
	cd web-app && npx vercel --prod 

web-locally: #uses fast api for model inferance
	(make embed-server & sleep 4) && \
	make web-dev
