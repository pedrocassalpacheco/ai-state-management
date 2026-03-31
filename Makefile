.PHONY: help up down restart logs logs-tidb logs-pd logs-tikv status clean \
        connect connect-tidb0 connect-tidb1 connect-tidb2 dashboard haproxy-stats health \
        init-db init-db-colocated init-both-dbs reset-db \
        ollama-pull ollama-serve ollama-test ollama-list ollama-setup \
        generate-data load-data load-data-colocated \
        seed-db seed-db-colocated seed-dbs setup-dbs \
        demo-placement test-resilience \
        docs-erd docs-erd-open

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

up: ## Start the TiDB cluster
	docker-compose up -d
	@echo "TiDB cluster is starting..."
	@echo "Wait 30-60 seconds for all services to be ready"
	@echo ""
	@echo "Connect to cluster:"
	@echo "  mysql -h 127.0.0.1 -P 3306 -u root"
	@echo "  (or use: make connect)"
	@echo ""
	@echo "Monitoring:"
	@echo "  HAProxy Stats: http://localhost:8080"
	@echo "  TiDB Dashboard: http://localhost:2383/dashboard/ (or 2379/2381)"
	@echo ""
	@echo "Direct TiDB instances (for debugging):"
	@echo "  - tidb0: localhost:4000"
	@echo "  - tidb1: localhost:4001"
	@echo "  - tidb2: localhost:4002"

down: ## Stop the TiDB cluster
	docker-compose down

restart: ## Restart the TiDB cluster
	docker-compose restart

logs: ## View logs from all services
	docker-compose logs -f

logs-tidb: ## View logs from TiDB instances only
	docker-compose logs -f tidb0 tidb1 tidb2

logs-pd: ## View logs from PD instances only
	docker-compose logs -f pd0 pd1 pd2

logs-tikv: ## View logs from TiKV instances only
	docker-compose logs -f tikv0 tikv1 tikv2

status: ## Show status of all services
	docker-compose ps

clean: ## Stop and remove all containers, networks, and volumes
	docker-compose down -v
	@echo "Cluster cleaned up. All data removed."

shell: ## Connect to TiDB via HAProxy load balancer (port 3306)
	mysqlsh --sql root@127.0.0.1:3306 --no-password

connect-tidb0: ## Connect to TiDB instance 0 (port 4000)
	mysqlsh -h 127.0.0.1 -P 4000 -u root --no-password

connect-tidb1: ## Connect to TiDB instance 1 (port 4001)
	mysqlsh -h 127.0.0.1 -P 4001 -u root --no-password

connect-tidb2: ## Connect to TiDB instance 2 (port 4002)
	mysqlsh -h 127.0.0.1 -P 4002 -u root --no-password

dashboard: ## Open TiDB Dashboard in browser
	@echo "Opening TiDB Dashboard at http://localhost:2383/dashboard/"
	@open http://localhost:2383/dashboard/ || xdg-open http://localhost:2383/dashboard/ || echo "Please open http://localhost:2383/dashboard/ in your browser"

haproxy-stats: ## Open HAProxy stats page in browser
	@echo "Opening HAProxy stats at http://localhost:8080"
	@open http://localhost:8080 || xdg-open http://localhost:8080 || echo "Please open http://localhost:8080 in your browser"

health: ## Check health of all services
	@echo "Checking TiDB instances..."
	@docker-compose exec tidb0 /tidb-server -V 2>/dev/null && echo "✓ TiDB0 is healthy" || echo "✗ TiDB0 is not responding"
	@docker-compose exec tidb1 /tidb-server -V 2>/dev/null && echo "✓ TiDB1 is healthy" || echo "✗ TiDB1 is not responding"
	@docker-compose exec tidb2 /tidb-server -V 2>/dev/null && echo "✓ TiDB2 is healthy" || echo "✗ TiDB2 is not responding"

init-db: ## Initialize database schema (creates tables)
	@echo "Initializing database schema..."
	@./scripts/init_db.sh

init-db-colocated: ## Initialize colocated database with placement rules (for user-bot conversation colocation)
	@echo "Initializing colocated database schema with placement rules..."
	@./scripts/init_db_colocated.sh

init-dbs: init-db init-db-colocated ## Initialize both regular and colocated databases

reset-dbs: ## Reset database (WARNING: drops all data!)
	@echo "⚠️  WARNING: This will delete ALL data in BOTH databases!"
	@echo "  • ai_memory (regular database)"
	@echo "  • ai_memory_colocated (colocated database)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		mysql -h 127.0.0.1 -P 3306 -u root -e "DROP DATABASE IF EXISTS ai_memory; DROP DATABASE IF EXISTS ai_memory_colocated;"; \
		echo "✓ Both databases dropped."; \
		echo ""; \
		echo "To recreate:"; \
		echo "  • make init-db           (regular database only)"; \
		echo "  • make init-db-colocated (colocated database only)"; \
		echo "  • make init-both-dbs     (both databases)"; \
	else \
		echo "Cancelled."; \
	fi

# Ollama Embedding Model Management
ollama-pull: ## Download nomic-embed-text embedding model
	@echo "Downloading nomic-embed-text model..."
	@ollama pull nomic-embed-text
	@echo "✓ Model downloaded successfully"
	@echo ""
	@echo "Model info:"
	@ollama show nomic-embed-text

ollama-serve: ## Start Ollama service (if not running)
	@echo "Checking Ollama service..."
	@if ! pgrep -x ollama >/dev/null; then \
		echo "Starting Ollama service..."; \
		ollama serve & \
		sleep 3; \
		echo "✓ Ollama service started"; \
	else \
		echo "✓ Ollama service is already running"; \
	fi

ollama-list: ## List all downloaded Ollama models
	@ollama list

ollama-test: ## Test embedding generation with nomic-embed-text
	@echo "Testing nomic-embed-text model..."
	@echo ""
	@curl -s http://localhost:11434/api/embeddings -d '{ \
	  "model": "nomic-embed-text", \
	  "prompt": "This is a test conversation between a user and an AI assistant." \
	}' | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'✓ Generated embedding with {len(data[\"embedding\"])} dimensions'); print(f'Sample values: {data[\"embedding\"][:5]}...')" 2>/dev/null || echo "✗ Failed to generate embedding. Make sure Ollama is running and model is pulled."

ollama-setup: ollama-serve ollama-pull ollama-test ## Complete Ollama setup (serve + pull + test)

# Test Data Generation and Loading
generate-data: ## Generate test dataset (1000+ conversation states with embeddings)
	@echo "Generating test data..."
	@echo "This will take several minutes to generate embeddings..."
	@python3 scripts/generate_test_data.py

load-data: ## Load generated test data into TiDB (regular database)
	@echo "Loading test data into ai_memory database..."
	@TIDB_DATABASE=ai_memory python3 scripts/load_test_data.py

load-data-colocated: ## Load generated test data into colocated database
	@echo "Loading test data into ai_memory_colocated database..."
	@TIDB_DATABASE=ai_memory_colocated python3 scripts/load_test_data.py

seed-db: generate-data load-data ## Generate and load test data into regular database

seed-db-colocated: generate-data load-data-colocated ## Generate and load test data into colocated database

seed-dbs: generate-data load-data load-data-colocated ## Generate and load test data into BOTH databases

setup-dbs: init-dbs seed-dbs ## Complete setup: initialize both databases and load test data

demo-placement: ## Demonstrate placement rules and data resilience
	@echo "Running placement rules demonstration..."
	@python3 scripts/demo_placement.py

test-resilience: ## Test data resilience by stopping a TiKV node
	@echo "Testing data resilience..."
	@echo "Current TiKV nodes status:"
	@docker-compose ps tikv0 tikv1 tikv2
	@echo ""
	@echo "Stopping tikv0..."
	@docker-compose stop tikv0
	@sleep 3
	@echo ""
	@echo "Running query test (should still work with 2/3 nodes)..."
	@python3 scripts/demo_placement.py
	@echo ""
	@echo "Restarting tikv0..."
	@docker-compose start tikv0
	@echo "✓ Resilience test complete!"

# Documentation
docs-erd: ## Generate ER diagram image from Mermaid file (requires mermaid-cli: npm install -g @mermaid-js/mermaid-cli)
	@if command -v mmdc >/dev/null 2>&1; then \
		echo "Generating ER diagram..."; \
		mmdc -i docs/schema-erd.mmd -o docs/schema-erd.png -b transparent; \
		echo "✓ Generated docs/schema-erd.png"; \
	else \
		echo "✗ mermaid-cli not installed"; \
		echo ""; \
		echo "Install with: npm install -g @mermaid-js/mermaid-cli"; \
		echo ""; \
		echo "Or view the diagram in:"; \
		echo "  • VS Code (install Mermaid extension)"; \
		echo "  • GitHub (renders automatically)"; \
		echo "  • https://mermaid.live (paste contents of docs/schema-erd.mmd)"; \
		exit 1; \
	fi

docs-erd-open: ## Open ER diagram in Mermaid Live Editor
	@echo "Opening Mermaid Live Editor..."
	@echo "Paste the contents of docs/schema-erd.mmd into the editor"
	@open https://mermaid.live || xdg-open https://mermaid.live || echo "Please open https://mermaid.live in your browser"
