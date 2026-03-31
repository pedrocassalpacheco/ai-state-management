# Scripts Directory

This directory contains scripts for managing the AI State Management database.

## Scripts

### `init_db.sh`
Initializes the database schema by executing `init_schema.sql`.

**Usage:**
```bash
make init-db
# Or directly:
./scripts/init_db.sh
```

### `generate_test_data.py`
Generates realistic test data for development and testing.

**What it creates:**
- 100 users with realistic names
- 15 different bot types
- Multiple sessions per user
- Realistic conversation messages
- 1000+ memory snapshots with embeddings

**Usage:**
```bash
make generate-data
# Or directly:
python3 scripts/generate_test_data.py
```

**Output:** JSONL files in `data/seed/`
- `users.jsonl`
- `bots.jsonl`
- `sessions.jsonl`
- `messages.jsonl`
- `memory_snapshots.jsonl`

**Note:** Embedding generation takes 5-10 minutes as each snapshot requires calling Ollama's nomic-embed-text model.

### `load_test_data.py`
Loads generated test data into TiDB database.

**Usage:**
```bash
make load-data
# Or directly:
python3 scripts/load_test_data.py
```

**Requirements:**
- TiDB cluster must be running
- Database schema must be initialized
- Test data must be generated first

**Features:**
- Batch inserts for performance (100 records per batch)
- Respects foreign key constraints
- Shows progress during loading
- Reports before/after record counts

## Complete Workflow

```bash
# 1. Start TiDB cluster
make up

# 2. Initialize database schema
make init-db

# 3. Make sure Ollama is running
make ollama-serve

# 4. Generate and load test data (one command)
make seed-db

# Or step by step:
make generate-data  # Generate JSONL files
make load-data      # Load into TiDB
```

## Data Structure

The generated data follows this relationship:

```
users (100)
  └─> sessions (200-800)
       ├─> messages (2000-40000)
       └─> memory_snapshots (1000+)
            └─> embeddings (768 dimensions each)

bots (15)
  └─> sessions (shared with users)
```

Each memory snapshot contains:
- Conversation summary
- Key facts (JSON object)
- Vector embedding (768-dim array)
- Importance score (0.0-1.0)
- Topics and entities

## Tips

- **Regenerate data:** Delete `data/seed/*.jsonl` files and run `make generate-data` again
- **Clear database:** Run `make reset-db` to drop all data
- **Partial load:** Edit `load_test_data.py` to load only specific tables
- **Performance:** Loading 1000+ snapshots takes 1-2 minutes


This directory contains utility scripts for managing the TiDB database.

## Available Scripts

### `init_db.sh`
Initializes the database schema by executing `init_schema.sql`.

**Usage:**
```bash
# Using Make (recommended)
make init-db

# Direct execution
./scripts/init_db.sh

# With custom host/port
TIDB_HOST=localhost TIDB_PORT=4000 ./scripts/init_db.sh
```

**Environment Variables:**
- `TIDB_HOST` - TiDB host (default: 127.0.0.1)
- `TIDB_PORT` - TiDB port (default: 3306 - HAProxy load balancer)
- `TIDB_USER` - TiDB user (default: root)
- `TIDB_PASSWORD` - TiDB password (default: empty)

### `init_schema.sql`
SQL file containing the complete database schema including:
- `users` - User accounts
- `bots` - Chatbot configurations
- `sessions` - Conversation sessions
- `messages` - Individual chat messages
- `memory_snapshots` - Vector-enabled memory storage
- `user_preferences` - User settings
- `usage_stats` - Analytics data

## Workflow

1. **Start TiDB cluster:**
   ```bash
   make up
   ```

2. **Wait for cluster to be ready** (30-60 seconds)

3. **Initialize schema:**
   ```bash
   make init-db
   ```

4. **Connect and verify:**
   ```bash
   make connect  # Connects through HAProxy load balancer
   USE ai_memory;
   SHOW TABLES;
   ```

## Notes

- The schema uses JSON columns for flexible metadata storage
- Vector embeddings are currently stored as JSON (will migrate to VECTOR type when fully supported)
- All timestamps use UTC by default
- Foreign key constraints ensure referential integrity
