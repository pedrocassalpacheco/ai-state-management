# Load environment variables from .env file
-include .env
export

.PHONY: help up down restart logs logs-tidb logs-pd logs-tikv status clean \
        connect connect-tidb0 connect-tidb1 connect-tidb2 dashboard haproxy-stats health \
        init-db-aurora init-db-tidb init-dbs reset-db-aurora reset-db-tidb reset-dbs \
        ollama-pull ollama-serve ollama-test ollama-list ollama-setup \
        generate-data load-data load-data-colocated \
        seed-db seed-db-colocated seed-dbs setup-dbs \
        demo-placement test-resilience \
        docs-erd docs-erd-open \
        chatbot-sim chatbot-sim-tidb

#
# Cluster Management
#
up: ## Start the TiDB cluster
	docker-compose up -d
	@echo "TiDB cluster is starting..."
	@echo ""

down: ## Stop the TiDB cluster
	docker-compose down
	@echo "TiDB cluster is stopping..."
	@echo ""

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

tidb: ## Connect to TiDB via HAProxy load balancer (port 3306)
	mysqlsh --sql root@127.0.0.1:3306 --no-password

aurora: ## Connect to Aurora RDS MySQL (port 3306)
	mysqlsh -h $(AURORA_HOST) -P $(AURORA_PORT) -u $(AURORA_USER) -p$(AURORA_PASSWORD) --ssl-mode=VERIFY_IDENTITY --ssl-ca=./global-bundle.pem

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

#
# Database Initialization and Reset
#
init-db-aurora: ## Initialize ai_memory database on Aurora RDS MySQL
	@echo "Initializing ai_memory database (Aurora RDS MySQL)..."
	@./scripts/init_db.sh aurora

init-db-tidb: ## Initialize ai_memory_colocated database on TiDB (partitioned)
	@echo "Initializing ai_memory_colocated database (TiDB partitioned)..."
	@./scripts/init_db.sh tidb

init-dbs: init-db-aurora init-db-tidb ## Initialize both databases (Aurora + TiDB)

reset-db-aurora: ## Reset Aurora database (WARNING: drops all data!)
	@./scripts/reset_db.sh aurora

reset-db-tidb: ## Reset TiDB database (WARNING: drops all data!)
	@./scripts/reset_db.sh tidb

reset-dbs: ## Reset both databases (WARNING: drops all data!)
	@echo "⚠️  WARNING: This will reset BOTH databases!"
	@echo ""
	@./scripts/reset_db.sh aurora
	@echo ""
	@./scripts/reset_db.sh tidb
#
# Ollama Embedding Model Management
#
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

ollama-setup: ollama-serve ollama-pull ollama-test ## Complete Ollama setup (serve + pull + test)

#
# Data Generation and Loading
#
generate-data: ## Generate test dataset (1000+ conversation states with embeddings)
	@echo "Generating test data..."
	@echo "This will take several minutes to generate embeddings..."
	@uv run python scripts/generate_test_data.py

load-data-aurora: ## Load generated test data into Aurora (non-partitioned)
	@echo "Loading test data into Aurora (ai_state_management)..."
	@uv run python scripts/load_test_data.py aurora

load-data-tidb: ## Load generated test data into TiDB (partitioned)
	@echo "Loading test data into TiDB (ai_state_management - partitioned)..."
	@uv run python scripts/load_test_data.py tidb

seed-db-tidb: generate-data load-data-tidb ## Generate and load test data into TiDB

seed-db-aurora: generate-data load-data-aurora ## Generate and load test data into Aurora

seed-dbs: generate-data load-data-aurora load-data-tidb ## Generate and load test data into both databases

#
# Chatbot Simulation
#
# Number of conversations to simulate (default: 5)
NUM_CONVERSATIONS ?= 5

chatbot-sim: ## Run chatbot simulation on Aurora (default: 5 random user-bot conversations)
	@echo "Running $(NUM_CONVERSATIONS) random conversations on Aurora (ai_state_management)..."
	@uv run python -m chatbot.simulator aurora $(NUM_CONVERSATIONS)

chatbot-sim-tidb: ## Run chatbot simulation on TiDB (default: 5 random user-bot conversations)
	@echo "Running $(NUM_CONVERSATIONS) random conversations on TiDB (ai_state_management - partitioned)..."
	@uv run python -m chatbot.simulator tidb $(NUM_CONVERSATIONS)
