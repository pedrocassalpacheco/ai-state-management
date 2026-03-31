# AI State Management with TiDB

A distributed state management system for AI chatbots using TiDB for long-term memory persistence.

## Architecture

This project uses a TiDB cluster with:
- **3 PD instances** (Placement Driver) - for cluster management and scheduling
- **3 TiKV instances** - distributed key-value storage layer
- **3 TiDB instances** - MySQL-compatible SQL interface
- **HAProxy** - Load balancer distributing connections across all TiDB instances

### Connection Architecture

```
┌─────────────┐
│ Application │
└──────┬──────┘
       │ port 3306
       ▼
┌─────────────────────┐
│  HAProxy (LB)       │
│  Round-robin        │
└──────┬──────────────┘
       │
   ┌───┴───────┬───────────┐
   ▼           ▼           ▼
┌──────┐   ┌──────┐   ┌──────┐
│tidb0 │   │tidb1 │   │tidb2 │  (Stateless SQL layer)
│:4000 │   │:4001 │   │:4002 │
└───┬──┘   └───┬──┘   └───┬──┘
    │          │          │
    └──────────┼──────────┘
               ▼
    ┌───────────────────────┐
    │   TiKV Cluster        │  (Distributed storage)
    │   tikv0, tikv1, tikv2 │
    └───────────────────────┘
```

All TiDB instances connect to the same distributed TiKV storage, so they all access the same data. HAProxy distributes client connections across the TiDB instances for load balancing and high availability.

## Quick Start

### Start the TiDB Cluster

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

The cluster takes 2-3 minutes to fully initialize. Wait for all services to be healthy.

**Connection Points:**
- **Port 3306** - HAProxy load balancer (recommended for applications)
- **Port 8080** - HAProxy stats dashboard
- Ports 4000, 4001, 4002 - Direct TiDB instances (for debugging)
- **Port 2333** - TiDB monitoring dashboard

### Initialize the Database Schema

Once the cluster is running, create the database schema:

```bash
# Initialize schema with all tables
make init-db
```

This will create the `ai_memory` database with tables for users, sessions, messages, and memory snapshots.

**📖 See [docs/SCHEMA.md](docs/SCHEMA.md) for complete schema documentation and data dictionary.**

### Connect to TiDB

**Recommended: Connect through the load balancer (port 3306)**

```bash
# Using MySQL client through load balancer
mysql -h 127.0.0.1 -P 3306 -u root

# Or use the make target
make connect  # Connects through load balancer

# Using Python
pip install pymysql
python
>>> import pymysql
>>> conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', database='ai_memory')
```

**For debugging: Connect to individual TiDB instances**

```bash
make connect-tidb1  # Direct connection to tidb0 (port 4000)
make connect-tidb2  # Direct connection to tidb1 (port 4001)
make connect-tidb3  # Direct connection to tidb2 (port 4002)
```

### Access TiDB Dashboard

The monitoring dashboard  through load balancer
mysql -h 127.0.0.1 -P 3306 -u root -e "SELECT VERSION();"

# View HAProxy stats (see which TiDB instances are up)
open http://localhost:8080

# Verify database and tables
mysql -h 127.0.0.1 -P 3306 -u root -e "USE ai_memory; SHOW TABLES;"

# Test distributed writes (write once, read from any instance)
mysql -h 127.0.0.1 -P 3306 -u root -e "USE ai_memory; INSERT INTO bots (bot_id, bot_name, bot_type) VALUES ('test-bot', 'Test Bot', 'test');"
mysql -h 127.0.0.1 -P 4001 -u root -e "USE ai_memory; SELECT * FROM bots WHERE bot_id='test-bot';"

# Test load balancing (HAProxy distributes connections)
for i in {1..6}; do
  echo "Connection $i:"
  mysql -h 127.0.0.1 -P 3306

| Service | Port(s) | Purpose |
|---------|---------|---------|haproxy | 3306, 8080 | Load balancer, Stats UI |
| tidb0 | 4000, 10080 | SQL interface, Status API |
| tidb1 | 4001, 10081 | SQL interface, Status API |
| tidb2 | 4002, 10082 | SQL interface, Status API |
| pd0 | 2379, 2380 | PD client, PD peer |
| pd1 | 2381, 2382 | PD client, PD peer |
| pd2 | 2383, 2384 | PD client, PD peer |
| tikv0 | 20160 | TiKV server |
| tikv1 | 20161 | TiKV server |
| tikv2 | 20162 | TiKV server |
| dashboard | 2333 | Monitoring UI |

## Testing the Cluster

```bash
# Test basic connectivity
mysql -h 127.0.0.1 -P 4000 -u root -e "SELECT VERSION();"

# Verify database and tables
mysql -h 127.0.0.1 -P 4000 -u root -e "USE ai_memory; SHOW TABLES;"

# Test distributed writes (should work on any TiDB instance)
mysql -h 127.0.0.1 -P 4000 -u root -e "USE ai_memory; INSERT INTO bots (bot_id, bot_name, bot_type) VALUES ('test-bot', 'Test Bot', 'test');"
mysql -h 127.0.0.1 -P 4001 -u root -e "USE ai_memory; SELECT * FROM bots WHERE bot_id='test-bot';"

# Test load balancing by connecting to different ports
for port in 4000 4001 4002; do
  echo "Testing port $port..."
  mysql -h 127.0.0.1 -P $port -u root -e "SELECT @@hostname;"
done
```

## Available Make Commands

```bash
make help           # Show all available commands
make up             # Start the TiDB cluster
make down           # Stop the TiDB cluster
make status         # Show status of all services
make logs           # View logs from all services
make init-db        # Initialize database schema
make reset-db       # Reset database (WARNING: deletes all data)
make connect        # Connect through load balancer (recommended)
make shell          # Connect using MySQL Shell
make connect-tidb1  # Connect to TiDB instance 1 (debugging)
make connect-tidb2  # Connect to TiDB instance 2 (debugging)
make connect-tidb3  # Connect to TiDB instance 3 (debugging)
make dashboard      # Open TiDB Dashboard
make haproxy-stats  # Open HAProxy stats page
make health         # Check health of all services
make clean          # Stop and remove all containers and data

# Ollama Embedding Model
make ollama-setup   # Complete setup: start Ollama + pull model + test
make ollama-serve   # Start Ollama service
make ollama-pull    # Download nomic-embed-text model
make ollama-list    # List downloaded models
make ollama-test    # Test embedding generation

# Testing
make notebook       # Open test notebook (TiDB + Ollama integration)

# Test Data Generation
make generate-data  # Generate test dataset (1000+ states with embeddings)
make load-data      # Load generated data into TiDB
make seed-db        # Generate and load test data (complete workflow)

# Placement Rules & Data Colocation
make init-db-placement  # Initialize schema with bot-based data colocation
make demo-placement     # Demonstrate placement rules and performance
make test-resilience    # Test data resilience by stopping a TiKV node
```

## Advanced: Placement Rules for Data Colocation

TiDB supports **placement rules** to control where data is physically stored. We use this to colocate all messages for a single bot on the same shard/partition.

**Benefits:**
- 🚀 5-10x faster queries for bot-specific data
- 📍 All related data stored together (locality)
- 💪 3 replicas ensure no data loss if nodes fail
- 📊 Even distribution across partitions

### Setup with Placement Rules

```bash
# 1. Initialize schema with placement rules
make init-db-placement

# 2. Generate and load test data
make seed-db

# 3. Verify placement and performance
make demo-placement
```

### Test Resilience

```bash
# Automated test: stops tikv0, runs queries, restarts
make test-resilience

# Manual: stop a node and see queries still work
docker-compose stop tikv0
make demo-placement  # Still works!
docker-compose start tikv0
```

**See [docs/PLACEMENT_RULES.md](docs/PLACEMENT_RULES.md) for complete documentation.**

## Troubleshooting

### Services won't start
```bash
# Check if ports are already in use
lsof -i :4000,4001,4002,2379

# Check logs for specific service
docker-compose logs pd0
docker-compose logs tikv0
docker-compose logs tidb0
```

### Cluster initialization taking too long
- TiDB cluster needs 2-3 minutes to fully initialize
- Check that all PD instances are up first: `docker-compose ps | grep pd`
- Then verify TiKV: `docker-compose ps | grep tikv`
- Finally TiDB: `docker-compose ps | grep tidb`

### Clean restart
```bash
docker-compose down
rm -rf data/
docker-compose up -d
```

## Ollama Embedding Model

This project uses **Ollama** with the **nomic-embed-text** model for generating embeddings from conversation text. These embeddings enable semantic search across conversation memories.

### Setup Ollama

```bash
# Complete setup (recommended for first time)
make ollama-setup

# Or step by step:
make ollama-serve   # Start Ollama service
make ollama-pull    # Download nomic-embed-text model
make ollama-test    # Test embedding generation
```

### About nomic-embed-text

- **Dimensions:** 768
- **Context Length:** 8,192 tokens
- **Use Case:** Text embeddings for semantic search
- **API Endpoint:** http://localhost:11434

### Generate Embeddings

```bash
# Via curl
curl http://localhost:11434/api/embeddings -d '{
  "model": "nomic-embed-text",
  "prompt": "Your conversation text here"
}'

# Via Python (using Ollama SDK)
import ollama
response = ollama.embeddings(
    model='nomic-embed-text',
    prompt='Your conversation text here'
)
embedding = response['embedding']  # 768-dimensional vector
```

### Test Notebook

A comprehensive Jupyter notebook is included that demonstrates:
- Connecting to TiDB cluster
- Running SQL queries
- Testing DeepSeek chat model
- Generating embeddings with nomic-embed-text
- Storing embeddings in TiDB

```bash
# Open the test notebook
make notebook

# Or open directly
jupyter notebook test_tidb_ollama.ipynb
```

## Test Data Generation

Generate a realistic dataset for testing and development with 1000+ conversation states.

### Quick Start

```bash
# Generate and load test data (complete workflow)
make seed-db
```

This will:
1. Generate 100 users, 15 bots, multiple sessions
2. Create realistic conversations with messages
3. Generate embeddings for 1000+ memory snapshots
4. Load everything into TiDB

### Manual Steps

```bash
# Step 1: Generate JSONL files (takes 5-10 minutes for embeddings)
make generate-data

# Step 2: Load data into TiDB
make load-data
```

### Dataset Details

The generated dataset includes:
- **100 users** with realistic names and metadata
- **15 bots** of different types (assistant, support, technical, coding, etc.)
- **200-800 sessions** with multiple conversations per user
- **2000-40000 messages** in realistic conversation flows
- **1000+ memory snapshots** each with 768-dimensional embeddings

**Features:**
- Users have multiple conversations with different bots
- Some users return to the same bots (simulating real usage)
- Each memory snapshot includes:
  - Conversation summary
  - Key facts (JSON)
  - Vector embedding (768 dimensions via nomic-embed-text)
  - Importance score
  - Topics and entities

**Data Files:** `data/seed/*.jsonl`
- `users.jsonl` - User accounts
- `bots.jsonl` - Bot configurations  
- `sessions.jsonl` - Conversation sessions
- `messages.jsonl` - Individual messages
- `memory_snapshots.jsonl` - Memory states with embeddings

## Next Steps

1. Review the [database schema documentation](docs/SCHEMA.md) to understand table relationships
2. Implement the memory snapshot system
3. Add vector search capabilities
4. Build the API layer

## Resources

- [TiDB Documentation](https://docs.pingcap.com/tidb/stable)
- [TiDB Vector Search](https://docs.pingcap.com/tidb/stable/vector-search)
- [Database Schema & Data Dictionary](docs/SCHEMA.md) - Comprehensive schema documentation
- [Placement Rules Documentation](docs/PLACEMENT_RULES.md) - Data colocation strategy
- [System Design Document](design.md) - Architecture overview
