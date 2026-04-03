# AI State Management - CDC-Based Dual Database Architecture

A distributed state management system for AI chatbots using **Change Data Capture (CDC)** for real-time replication between Aurora RDS (source) and TiDB (replica). Demonstrates best practices for hybrid cloud database architecture with high-availability data synchronization.

## Overview

This project implements a **source-replica pattern** where:
- **Aurora RDS MySQL** serves as the source database (primary writes)
- **TiDB** serves as a replicated OLTP-optimized clone (secondary reads)
- **TiDB Data Migration (DM)** keeps data synchronized in near real-time via CDC

This architecture combines operational simplicity (single write endpoint at Aurora) with analytical and caching benefits (fast reads from TiDB).

## Architecture

### Deployment Diagram

```
┌─────────────┐
│ Application │
│   (Write)   │
└──────┬──────┘
       │
       v
┌──────────────────────────┐
│  Aurora RDS MySQL        │ (AWS Managed Service - MySQL 8.0.x)
│  ai_state_management     │
│  • Source database       │
│  • Captures binlog       │
│  • Single write endpoint │
└──────────┬───────────────┘
           │
           │ CDC via TiDB Data Migration (DM)
           │ • dm-master (orchestrator)
           │ • dm-worker (replicates binlog)
           │
           v
┌──────────────────────────────────────────────────────────┐
│            TiDB Cluster (Docker Containers)              │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ HAProxy Load Balancer (port 3306)                │   │
│  │ • Round-robin across TiDB instances              │   │
│  │ • Health checks & automatic failover             │   │
│  └────────┬──────────────────────────────────────┬──┘   │
│           │                  │                    │      │
│       ┌───▼──┐           ┌───▼──┐            ┌───▼──┐   │
│       │tidb0 │           │tidb1 │            │tidb2 │   │
│       │:4000 │           │:4001 │            │:4002 │   │
│       └────┬─┘           └────┬─┘            └────┬─┘   │
│           │                   │                    │     │
│           └───────────────────┼────────────────────┘     │
│                               │                          │
│                   ┌───────────▼────────────┐             │
│                   │   TiKV Cluster         │             │
│                   │   (Storage Layer)      │             │
│                   │ • 3-way replication    │             │
│                   │ • Raft consensus       │             │
│                   │ • Partitioned data     │             │
│                   └────────────────────────┘             │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │ PD Cluster (Placement Driver)                    │   │
│  │ • Metadata & topology management                 │   │
│  │ • Timestamp oracle                               │   │
│  │ • Region scheduling                              │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  Database: ai_state_management (identical to Aurora)     │
│  • Partitioned by session_id for query optimization    │
│  • 3x data replication via Raft                        │
│  • ACID transactions with distributed consensus        │
│                                                          │
└──────────────────────────────────────────────────────────┘
       ▲
       │ (Read)
       │
┌──────┴──────────────────────┐
│ Application                  │
│ • Fast reads from replicas   │
│ • Session-optimized queries  │
│ • High-traffic OLTP queries  │
└──────────────────────────────┘
```

### Why This Architecture?

| Aspect | Aurora (Source) | TiDB (Replica) |
|--------|-----------------|------------------|
| **Role** | Primary writes | Secondary reads, caching |
| **Schema** | Normalized | Denormalized, partitioned |
| **Location** | AWS cloud (managed) | Self-hosted containers |
| **Partitioning** | None (full table scans) | By session_id (pruned queries) |
| **Best for** | Analytics, BI, cross-user queries | User-specific queries, caching |
| **CDC Sync** | Source of truth | Replicated near real-time |
| **Write Latency** | ✓ Direct from app | ✗ Must go through Aurora first |
| **Read Latency** | ✗ Network to AWS | ✓ Local container, faster |

### Data Synchronization Flow

```
1. Application writes to Aurora
   Application → Aurora (INSERT/UPDATE/DELETE)

2. Aurora captures changes in binlog
   Binlog: "user 123 sent a message to bot xyz"

3. TiDB DM reads binlog continuously
   dm-worker tail -f aurora_binlog

4. DM applies change to TiDB
   Apply same INSERT/UPDATE/DELETE to TiDB

5. Application can read from TiDB
   TiDB serves read requests with <1s lag
```

## Quick Start

### Prerequisites

1. **Docker & Docker Compose** - For TiDB cluster and DM services
2. **Aurora RDS MySQL 8.0.x** - AWS RDS instance (MySQL 8.4+ not supported by DM)
3. **MySQL/mysqlsh Client** - For database connections
4. **Python 3.8+** - For scripts (optional)

### Step 1: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and set Aurora credentials:
# AURORA_HOST=your-aurora-endpoint.rds.amazonaws.com
# AURORA_PORT=3306
# AURORA_USER=admin
# AURORA_PASSWORD=your-secure-password
# AURORA_DATABASE=ai_state_management
```

**Important:** Aurora must be MySQL 8.0.x (8.4+ incompatible with TiDB DM due to MASTER STATUS command changes)

### Step 2: Start TiDB Cluster

```bash
# Start TiDB cluster containers
docker-compose up -d

# Wait 2-3 minutes for cluster to initialize
docker-compose ps

# Verify all services are running
make health
```

### Step 3: Initialize Databases

```bash
# Initialize Aurora with schema
make init-db-aurora

# Initialize TiDB with schema (same structure as Aurora)
make init-db-tidb

# Or both at once
make init-dbs
```

### Step 4: Set Up CDC Replication

```bash
# Deploy DM cluster (dm-master, dm-worker containers)
make cdc-deploy

# Verify Aurora binlog configuration
make cdc-binlog

# Run full sync: dump Aurora → load to TiDB → start CDC
make cdc-full

# Monitor replication status
make cdc-status
```

Expected output:
```
Relay: Running (catching up with master)
Sync: Running (synced)
Lag: 0s
```

### Step 5: Load Test Data

```bash
# Generate test dataset
make generate-data

# Load into Aurora (writes happen here)
make load-data-aurora

# TiDB receives data via CDC automatically (within 1-5 seconds)
sleep 5

# Verify replication
mysql -h 127.0.0.1 -P 3306 -u root ai_state_management -e "SELECT COUNT(*) FROM users;"
```

### Step 6: Test CDC Replication

```bash
# Test insert in Aurora and verify in TiDB
make cdc-test

# Or manually test using the sanity_check notebook
# (Includes CDC replication test)
```

## Database Schema

### Two Schema Variants

This project uses **two different schemas optimized for different access patterns**:

#### Schema 1: Normalized (Aurora)
```
users ──┐
        ├──> sessions ──> messages (session_id only)
bots ──┘
```
- **Purpose:** Analytics, BI queries, cross-user reports
- **Joins:** Required (messages.session_id → sessions → users/bots)
- **Partitioning:** None
- **Best for:** "Show all conversations across all users"

#### Schema 2: Denormalized (TiDB)
```
users ──┐
        ├──> sessions ──> messages (session_id + user_id + bot_id)
bots ──┘     └─> PARTITIONED BY KEY(user_id, bot_id)
```
- **Purpose:** OLTP queries, user-specific data, high-traffic reads
- **Joins:** Often unnecessary (user_id, bot_id already in messages)
- **Partitioning:** By `(user_id, bot_id)` - 8 partitions
- **Best for:** "Get all messages for user X with bot Y"
- **Performance:** 5-10x faster for session retrieval due to partition pruning

### Core Tables

| Table | Rows | Purpose | Indexed By |
|-------|------|---------|-----------|
| **users** | 100+ | User accounts | user_id, username |
| **bots** | 15+ | Bot definitions | bot_id, bot_type |
| **sessions** | 200-800 | Conversations | (user_id, bot_id), status |
| **messages** | 2000-40000 | Message exchanges | (session_id, created_at), (user_id, bot_id) |
| **memory_snapshots** | 1000+ | Semantic summaries with embeddings | (session_id, created_at) |
| **usage_stats** | Variable | Token usage tracking | (user_id, bot_id, date) |

### Data Dictionary

#### users
- `user_id` (CHAR(36) PK) - UUID
- `username` (VARCHAR(255) UNIQUE) - Display name
- `email` (VARCHAR(255)) - Email address
- `created_at` (TIMESTAMP) - Account creation
- `last_active_at` (TIMESTAMP) - Last interaction
- `metadata` (JSON) - User preferences

#### bots
- `bot_id` (VARCHAR(100) PK) - Unique identifier
- `bot_name` (VARCHAR(255)) - Display name
- `bot_type` (VARCHAR(50)) - Category (assistant, support, etc)
- `system_prompt` (TEXT) - Bot behavior definition
- `config` (JSON) - Model settings
- `is_active` (BOOLEAN) - Active status

#### sessions
- `session_id` (CHAR(36) PK) - UUID
- `user_id` (CHAR(36) FK) - User in session
- `bot_id` (VARCHAR(100) FK) - Bot in session
- `started_at` (TIMESTAMP) - Session start
- `last_active_at` (TIMESTAMP) - Last message
- `ended_at` (TIMESTAMP) - Session end (NULL if active)
- `status` (VARCHAR(50)) - active/archived/deleted
- `message_count` (INT) - Total messages
- `total_tokens` (INT) - Total tokens used
- `metadata` (JSON) - Session metadata

**Partitioning (TiDB only):** `PARTITION BY KEY(user_id, bot_id) PARTITIONS 8`

#### messages
- `message_id` (BIGINT PK AUTO_INCREMENT) - Unique ID
- `session_id` (CHAR(36) FK) - Session reference
- `user_id` (CHAR(36)) - User (denormalized for partitioning)
- `bot_id` (VARCHAR(100)) - Bot (denormalized for partitioning)
- `role` (VARCHAR(50)) - user/assistant/system/tool
- `content` (TEXT) - Message text
- `created_at` (TIMESTAMP(6)) - Microsecond precision
- `tokens_used` (INT) - Token count
- `model` (VARCHAR(100)) - Model used (assistant only)
- `finish_reason` (VARCHAR(50)) - stop/length/tool_calls
- `metadata` (JSON) - Additional data

**Partitioning (TiDB only):** `PARTITION BY KEY(user_id, bot_id) PARTITIONS 8`

#### memory_snapshots
- `snapshot_id` (BIGINT PK AUTO_INCREMENT) - Unique ID
- `session_id` (CHAR(36) FK) - Session reference
- `user_id` (CHAR(36)) - User
- `bot_id` (VARCHAR(100)) - Bot
- `summary` (TEXT) - Conversation summary
- `key_facts` (JSON) - Important points
- `embedding` (VECTOR(768)) - Text embedding for semantic search
- `importance_score` (FLOAT) - Priority ranking
- `topics` (JSON) - Extracted topics/entities
- `created_at` (TIMESTAMP) - Creation time
- `message_count_when_created` (INT) - Messages at snapshot

#### usage_stats
- `stat_id` (BIGINT PK AUTO_INCREMENT) - Unique ID
- `user_id` (CHAR(36) FK) - User
- `bot_id` (VARCHAR(100) FK) - Bot
- `date` (DATE) - Statistics date
- `total_messages` (INT) - Messages on this date
- `total_tokens` (INT) - Tokens consumed
- `avg_response_time_ms` (FLOAT) - Average response time
- `error_count` (INT) - Errors encountered
- `updated_at` (TIMESTAMP) - Last update

## CDC Replication Commands

### Setup & Monitoring

```bash
make cdc-deploy      # Start DM cluster (dm-master, dm-worker)
make cdc-binlog      # Check Aurora binlog configuration
make cdc-full        # Full sync + CDC (initial replication)
make cdc-status      # Monitor replication status
make cdc-logs        # View DM worker logs
make cdc-test        # Test with sample INSERT
```

### Operational Commands

```bash
make cdc-pause       # Pause replication (keeps DM task, stops sync)
make cdc-resume      # Resume replication
make cdc-stop        # Stop replication (deletes DM task)
```

### Replication Status

Check status with:
```bash
make cdc-status
```

Status fields:
- **Relay:** Catching up with Aurora binlog
- **Sync:** Processing changes to TiDB
- **Synced:** True when fully caught up
- **Lag:** Seconds behind master (should be <1s in production)

## Database Connections

### Application Code (Python)

```python
import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

# Connection to Aurora (writes)
aurora_conn = pymysql.connect(
    host=os.getenv('AURORA_HOST'),
    port=int(os.getenv('AURORA_PORT', 3306)),
    user=os.getenv('AURORA_USER'),
    password=os.getenv('AURORA_PASSWORD'),
    database='ai_state_management'
)

# Connection to TiDB (reads - goes through HAProxy load balancer)
tidb_conn = pymysql.connect(
    host='127.0.0.1',
    port=3306,  # HAProxy, not TiDB directly
    user='root',
    database='ai_state_management'
)

# Write to Aurora
with aurora_conn.cursor() as cursor:
    cursor.execute("INSERT INTO messages (...) VALUES (...)")
    aurora_conn.commit()

# Read from TiDB (data arrives via CDC within 1-5 seconds)
with tidb_conn.cursor() as cursor:
    cursor.execute("SELECT * FROM sessions WHERE user_id = %s", (user_id,))
    rows = cursor.fetchall()
```

### MySQL Client

```bash
# Connect to Aurora (write endpoint)
mysql -h your-aurora-endpoint.rds.amazonaws.com -u admin -p ai_state_management

# Connect to TiDB (through HAProxy load balancer)
mysql -h 127.0.0.1 -P 3306 -u root ai_state_management

# Connect to specific TiDB instance (for debugging)
mysql -h 127.0.0.1 -P 4000 -u root ai_state_management  # tidb0
mysql -h 127.0.0.1 -P 4001 -u root ai_state_management  # tidb1
mysql -h 127.0.0.1 -P 4002 -u root ai_state_management  # tidb2
```

## Monitoring & Dashboards

| Dashboard | URL | Purpose |
|-----------|-----|---------|
| **HAProxy Stats** | http://localhost:8080 | Connection distribution, TiDB instance health |
| **TiDB Dashboard** | http://localhost:2383 | Cluster topology, query metrics, storage |

Open dashboards:
```bash
make haproxy-stats   # HAProxy statistics page
make dashboard       # TiDB dashboard
```

## TiDB Cluster Architecture

### Component Layout

```
┌── HAProxy (Load Balancer)
│   ├── Port 3306 (MySQL protocol)
│   └── Port 8080 (stats dashboard)
│
├── TiDB Nodes (Stateless SQL Layer)
│   ├── tidb0 (port 4000)
│   ├── tidb1 (port 4001)
│   └── tidb2 (port 4002)
│
├── PD Nodes (Placement Driver - Cluster Coordinator)
│   ├── pd0 (port 2379-2380)
│   ├── pd1 (port 2381-2382)
│   └── pd2 (port 2383-2384)
│
└── TiKV Nodes (Distributed Storage)
    ├── tikv0 (port 20160)
    ├── tikv1 (port 20161)
    └── tikv2 (port 20162)
```

### High Availability

- **TiDB:** Stateless, any instance can handle requests (HAProxy distributes)
- **PD:** 3-node quorum for metadata decisions
- **TiKV:** Raft consensus with 3x replication (survives 1 node loss)
- **HAProxy:** Health checks, automatic failover

## Test Data & Performance

### Generate Test Data

```bash
# Generate 100 users, 15 bots, 1000+ memory snapshots with embeddings
# (Takes 5-10 minutes)
make generate-data

# Load into Aurora (CDC will replicate to TiDB)
make load-data-aurora
```

### Test Performance

The project includes a `retriever.ipynb` notebook that compares:
- **Aurora** (normalized, no partitioning) vs **TiDB** (partitioned by session_id)
- Same 10 sessions, same queries
- Shows TiDB's partition-pruning optimization
- Expected speedup: 5-10x for session-specific queries

```bash
# Run performance comparison
jupyter notebook notebooks/retriever.ipynb
```

## Machine Learning Integration

### Embeddings (Ollama)

This project uses **Ollama** with **nomic-embed-text** model (768 dimensions) for semantic search:

```bash
# Setup Ollama (one-time)
make ollama-setup

# Generate embeddings in Python
import ollama
response = ollama.embeddings(
    model='nomic-embed-text',
    prompt='conversation text'
)
embedding = response['embedding']  # 768-dimensional vector

# Store in TiDB
cursor.execute(
    "INSERT INTO memory_snapshots (embedding) VALUES (%s)",
    (embedding,)
)
```

### Vector Search

```sql
-- Find similar memories (via TiDB vector search)
SELECT snapshot_id, similarity_score
FROM memory_snapshots
WHERE session_id = %s
ORDER BY VEC_DISTANCE(embedding, query_vector) ASC
LIMIT 5;
```

## Testing & Validation

### Sanity Check Notebook

Comprehensive validation notebook (`notebooks/sanity_check.ipynb`):
- ✓ Aurora connection test
- ✓ TiDB connection test
- ✓ Schema validation
- ✓ Foreign key integrity
- ✓ Data distribution check
- ✓ CDC replication test (insert in Aurora, verify in TiDB)

### Make Targets for Testing

```bash
make cdc-test                  # Test CDC replication
make test-resilience           # Stop a node, verify queries work
make health                    # Check all services are running
make status                    # Show container status
```

## Troubleshooting

### DM Cluster Issues

```bash
# Check DM services
docker-compose ps dm-master dm-worker

# View DM worker logs
make cdc-logs

# Restart DM cluster
docker-compose restart dm-master dm-worker
```

### Aurora Connection Issues

```bash
# Verify Aurora configuration in .env
cat .env | grep AURORA

# Test Aurora connection
mysql -h $AURORA_HOST -u $AURORA_USER -p$AURORA_PASSWORD -e "SELECT VERSION();"

# Check Aurora binlog settings
make cdc-binlog
```

### TiDB Cluster Won't Start

```bash
# Check which services are failing
docker-compose ps

# View PD logs (usually starts first)
docker-compose logs pd0 | head -50

# View TiDB logs (depends on PD)
docker-compose logs tidb0 | head -50

# Clean restart
docker-compose down
rm -rf data/
docker-compose up -d
```

### Replication Lag

```bash
# Check replication status
make cdc-status

# If lagging >5 seconds:
# 1. Check DM worker logs
make cdc-logs

# 2. Check TiKV storage space
docker-compose exec tidb0 mysql -u root -e "SELECT * FROM information_schema.cluster_info;"
```

## Project Structure

```
.
├── README.md                      # You are here
├── .env.example                   # Environment template
├── Makefile                       # Build automation
├── docker-compose.yml             # TiDB + DM cluster definition
│
├── docs/
│   ├── SCHEMA.md                 # (OLD - merged into README)
│   ├── schema-erd.mmd            # Entity-Relationship diagram
│   └── PLACEMENT_RULES.md         # Data colocation strategies
│
├── migration/
│   ├── README.md                 # (OLD - merged into main README)
│   ├── cdc_full_sync.sh          # CDC setup script
│   └── config/
│       ├── dm-source-aurora.yaml
│       └── dm-task-aurora-to-tidb-full.yaml
│
├── chatbot/
│   ├── __init__.py
│   ├── bot.py                    # Bot logic
│   ├── memory.py                 # Memory management
│   ├── session_manager.py         # Session handling
│   └── simulator.py              # Data generation
│
├── scripts/
│   ├── init_schema_aurora.sql    # Aurora schema
│   ├── init_schema_tidb.sql      # TiDB schema
│   ├── check_schemas.py          # Schema validation
│   ├── generate_test_data.py     # Test data generation
│   └── load_test_data.py         # Data loading
│
├── notebooks/
│   ├── sanity_check.ipynb        # Schema & replication verification
│   └── retriever.ipynb           # Performance comparison (Aurora vs TiDB)
│
└── data/
    ├── seed/                     # Test data (.jsonl files)
    ├── pd*/                      # PD data directories
    ├── tidb*/                    # TiDB data directories
    ├── tikv*/                    # TiKV data directories
    └── dm-*/                     # DM (Data Migration) state
```

## Available Make Commands

```bash
# Cluster Management
make up                    # Start TiDB cluster
make down                  # Stop TiDB cluster
make restart               # Restart cluster
make status                # Show service status
make health                # Check service health
make logs                  # View all logs
make clean                 # Stop and remove all data

# Database Setup
make init-db-aurora        # Initialize Aurora schema
make init-db-tidb          # Initialize TiDB schema
make init-dbs              # Initialize both

# Data Management
make generate-data         # Generate test dataset
make load-data-aurora      # Load data into Aurora
make load-data-tidb        # TiDB receives via CDC
make seed-dbs              # Generate and load all

# Connections
make connect               # Connect to TiDB via HAProxy
make connect-aurora        # Connect to Aurora

# CDC Replication
make cdc-deploy            # Start DM cluster
make cdc-binlog            # Check Aurora binlog
make cdc-full              # Full sync + CDC
make cdc-status            # Monitor replication
make cdc-pause             # Pause replication
make cdc-resume            # Resume replication
make cdc-stop              # Stop replication
make cdc-test              # Test CDC replication

# Monitoring
make dashboard             # Open TiDB dashboard
make haproxy-stats         # Open HAProxy stats

# ML/Embeddings  
make ollama-setup          # Setup Ollama + model
make ollama-serve          # Start Ollama service
make ollama-pull           # Download model

# Testing
make chatbot-sim           # Run chatbot simulator
make test-resilience       # Test node failure recovery
```

## Performance Characteristics

### Read Performance (TiDB Replica)

- **Average session retrieval:** 5-50ms (depends on session size)
- **Partition pruning:** Scans ~1/8 of data with dedicated columns
- **Speedup vs Aurora:** 5-10x for user-specific queries
- **Replication lag:** <1s (usually <100ms)

### Write Performance (Aurora Source)

- **Message insert:** 10-50ms to Aurora
- **Replication to TiDB:** <100ms for small changes, <5s for bulk loads
- **Consistency:** Eventually consistent (1-5 second lag)

### Cluster Capacity

- **Data capacity:** Petabytes (TiKV distributed storage)
- **Concurrent connections:** Thousands (HAProxy + TiDB stateless)
- **Throughput:** 100k+ ops/second
- **Replication:** 3x redundancy (survives 1 node loss)

## Next Steps

1. **Test CDC replication:** Run `make cdc-full && make cdc-test`
2. **Verify schema:** Check `sanity_check.ipynb` notebook
3. **Load test data:** Run `make generate-data && make load-data-aurora`
4. **Monitor performance:** Check `retriever.ipynb` for Aurora vs TiDB comparison
5. **Build application:** Integrate with your chatbot framework
6. **Setup monitoring:** Configure alerts on replication lag

## References

- [TiDB Documentation](https://docs.pingcap.com/tidb/stable)
- [TiDB Data Migration (DM)](https://docs.pingcap.com/tidb/stable/dm-overview)
- [TiDB Vector Search](https://docs.pingcap.com/tidb/stable/vector-search)
- [Ollama Documentation](https://github.com/ollama/ollama)
- [MySQL 8.0 Documentation](https://dev.mysql.com/doc/refman/8.0/en/)

## Architecture

### Aurora RDS MySQL (Cloud)
```
┌─────────────┐
│ Application │
└──────┬──────┘
       │ Aurora endpoint
       ▼
┌─────────────────────┐
│  Aurora RDS MySQL   │  (AWS Managed)
│  ai_memory          │  Normalized schema
└─────────────────────┘
```

### TiDB Cluster (Self-Hosted)

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

### Prerequisites

1. **Docker & Docker Compose** - For running TiDB cluster
2. **Aurora RDS MySQL** - AWS Aurora instance (optional, TiDB used as fallback)
3. **MySQL Client** - For database connections (`mysql` or `mysqlsh`)

### Step 1: Configure Environment

The project supports two setups:

**Option A: Aurora + TiDB (Recommended for Production)**
```bash
# Copy environment template
cp .env.example .env

# Edit .env and configure Aurora RDS MySQL credentials:
# AURORA_HOST=your-aurora-endpoint.rds.amazonaws.com
# AURORA_USER=admin
# AURORA_PASSWORD=your-password
```

**Option B: TiDB Only (Development/Testing)**
```bash
# No .env file needed - uses TiDB for both databases
# Just start the cluster (next step)
```

**Check your configuration:**
```bash
make check-config
# Shows which database will be used for each schema
```

### Step 2: Start the TiDB Cluster

```bash
# Start TiDB cluster for partitioned database
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
- **Port 2383** - TiDB monitoring dashboard

### Step 3: Initialize Both Databases

```bash
# Initialize Aurora RDS MySQL (ai_memory - non-partitioned)
make init-db-aurora

# Initialize TiDB (ai_memory_colocated - partitioned)
make init-db-colocated

# Or initialize both at once
make init-dbs-dual
```

This creates:
- **Aurora:** `ai_memory` database with normalized schema
- **TiDB:** `ai_memory_colocated` database with partitioned schema

**📖 See [docs/SCHEMA.md](docs/SCHEMA.md) for complete schema documentation and data dictionary.**

### Step 4: Load Test Data

```bash
# Generate test data
make generate-data

# Load into Aurora RDS MySQL
make load-data-aurora

# Load into TiDB partitioned database
make load-data-colocated

# Or load into both at once
make seed-db-aurora seed-db-colocated
```

### Connect to Databases

**Aurora RDS MySQL (Analytics):**

```bash
# Using environment variables
make connect-aurora

# Or directly with mysql client
mysql -h your-aurora-endpoint.rds.amazonaws.com -u admin -p ai_memory
```

**TiDB (Transactional) - Recommended: Connect through the load balancer (port 3306)**

```bash
# Using MySQL client through HAProxy load balancer
mysql -h 127.0.0.1 -P 3306 -u root

# Or use the make target
make connect  # Connects through load balancer

# Using Python
pip install pymysql
python
>>> import pymysql
>>> # Aurora connection
>>> aurora_conn = pymysql.connect(
...     host='your-aurora-endpoint.rds.amazonaws.com',
...     user='admin', password='your-password',
...     database='ai_memory'
... )
>>> # TiDB connection  
>>> tidb_conn = pymysql.connect(
...     host='127.0.0.1', port=3306,
...     user='root', database='ai_memory_colocated'
... )
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
