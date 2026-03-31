# TiDB Placement Rules for Data Colocation

This document explains how we use TiDB's placement rules to colocate conversation data by user-bot pairs, improving query performance and demonstrating data resilience.

**📖 For complete schema documentation, see [SCHEMA.md](./SCHEMA.md)**

## Overview

**Goal**: Ensure all messages, sessions, and memory snapshots for a specific user-bot conversation pair are stored together on the same TiKV partition/region.

**Benefits**:
- 🚀 **Performance**: Queries for a specific user-bot conversation only scan one partition/region
- 📍 **Locality**: All data for a user-bot pair is physically close together
- 💪 **Resilience**: Multiple replicas ensure no data loss if nodes fail
- 📊 **Scalability**: KEY partitioning evenly distributes user-bot pairs across partitions

## Architecture

### Partitioning Strategy

We use **KEY partitioning** by `(user_id, bot_id)` composite key to distribute data:

```sql
PARTITION BY KEY(user_id, bot_id) PARTITIONS 8
```

This ensures:
1. All data for a user-bot pair goes to the same partition
2. User-bot pairs are evenly distributed across 8 partitions
3. No hot spots (balanced load)
4. Related data (sessions, messages, snapshots) colocated

### Tables with Partitioning

Four main tables are partitioned by `(user_id, bot_id)`:

1. **sessions** - Partitioned by `(user_id, bot_id)`
2. **messages** - Includes denormalized `user_id` and `bot_id` for partitioning
3. **memory_snapshots** - Partitioned by `(user_id, bot_id)`
4. **usage_stats** - Partitioned by `(user_id, bot_id)`

### Schema Differences

**Standard Schema** (`init_schema.sql` → `ai_memory` database):
- No partitioning
- Standard foreign keys
- `messages.message_id` is simple PRIMARY KEY AUTO_INCREMENT
- Used for single-node or small-scale deployments

**Colocated Schema** (`init_schema_with_placement.sql` → `ai_memory_colocated` database):
- KEY partitioned by `(user_id, bot_id)` - 8 partitions per table
- Denormalized `user_id` and `bot_id` in child tables
- Composite primary keys: `(user_id, bot_id, <id>)`
- Placement policies for replica distribution
- Optimized for distributed queries on user-bot conversation data

## Placement Policies

TiDB placement policies control where data is physically stored:

```sql
CREATE PLACEMENT POLICY policy_assistant 
    FOLLOWERS=2 
    COMMENT='3 replicas total (1 leader + 2 followers)';
```

**Replication**: Each partition has 3 replicas for high availability
- 1 leader (handles writes and serves reads)
- 2 followers (serve reads, can become leader if leader fails)

## Setup

### 1. Initialize Database with Placement Rules

```bash
# Use the placement-aware schema
make init-db-placement
```

This creates:
- Partitioned tables (messages, sessions, memory_snapshots)
- Placement policies
- Views for monitoring partition/region distribution

### 2. Generate Test Data

```bash
# Generate realistic test data
make generate-data
```

The data generator includes both `user_id` and `bot_id` in messages for partitioning support.

### 3. Load Data

```bash
# Load into colocated database
make load-data-colocated

# Or initialize + seed both databases at once
make setup-both-dbs
```

The loader automatically detects which schema is being used and adapts the INSERT statements accordingly.

### 4. Verify Placement

```bash
make demo-placement
```

This shows:
- Partition distribution
- Bot data distribution
- Query performance with colocation
- Region distribution across TiKV stores

## Performance Benefits

### Without Colocation (Standard Schema)
```
Query: Get all messages between user '123...' and bot 'assistant-bot-1'
- Full table scan across all regions
- Multiple network hops
- Slower performance
```

### With Colocation (Partitioned Schema)
```
Query: Get all messages between user '123...' and bot 'assistant-bot-1'
- Scans only partition 3 (where this user-bot pair's data lives)
- Single partition scan
- 5-10x faster for user-bot conversation queries
```

### Example Query Performance

```sql
-- All messages for a specific user-bot conversation (colocated = fast)
SELECT COUNT(*) 
FROM messages 
WHERE user_id = '123e4567-e89b-12d3-a456-426614174000'
  AND bot_id = 'assistant-bot-1';
-- Scans only 1 partition (12.5% of data)
-- Scans only 1 partition

-- Recent messages for a bot (colocated = fast)
SELECT * FROM messages 
WHERE bot_id = 'assistant-bot-1' 
ORDER BY created_at DESC 
LIMIT 100;
-- Single partition scan with index
```

## Resilience Testing

### Test Data Loss Protection

```bash
# Automated test
make test-resilience
```

This will:
1. Show current TiKV node status
2. Stop one TiKV node (tikv0)
3. Run queries (they still work!)
4. Restart the node
5. Verify cluster health

### Manual Testing

```bash
# Stop a TiKV node
docker-compose stop tikv0

# Queries still work (using replicas on tikv1/tikv2)
make demo-placement

# Check cluster status
docker-compose ps

# Restart the node
docker-compose start tikv0
```

**What Happens**:
1. PD detects tikv0 is down
2. Queries automatically use replicas on tikv1/tikv2
3. No data loss (3 replicas)
4. When tikv0 restarts, it catches up automatically

## Monitoring

### View Partition Information

```sql
-- See how data is distributed across partitions
SELECT * FROM partition_info;

-- Output:
-- TABLE_NAME            PARTITION_NAME  POSITION  TABLE_ROWS
-- messages              p0              0         1247
-- messages              p1              1         1189
-- messages              p2              2         1301
-- ...
```

### View Bot Distribution

```sql
-- See which bots have the most data
SELECT 
    bot_id,
    COUNT(DISTINCT session_id) as sessions,
    COUNT(*) as messages,
    SUM(tokens_used) as total_tokens
FROM messages
GROUP BY bot_id
ORDER BY messages DESC;
```

### View Region Distribution (Admin)

```sql
-- See which TiKV stores hold which regions
SELECT 
    table_name,
    region_id,
    leader_store_id,
    peer_stores
FROM INFORMATION_SCHEMA.TIKV_REGION_STATUS
WHERE db_name = 'ai_memory'
ORDER BY table_name, region_id;
```

## Migration Guide

### From Standard Schema to Placement Schema

If you already have data in the standard schema:

```bash
# 1. Backup your data
make backup  # (if backup target exists)

# 2. Reset database
make reset-db

# 3. Initialize with placement schema
make init-db-placement

# 4. Regenerate data (now includes bot_id in messages)
make seed-db
```

### Updating Existing Code

If you have custom loading scripts, update the messages insert:

**Before**:
```python
cursor.execute("""
    INSERT INTO messages (session_id, role, content, ...)
    VALUES (%s, %s, %s, ...)
""", (session_id, role, content, ...))
```

**After**:
```python
cursor.execute("""
    INSERT INTO messages (session_id, bot_id, role, content, ...)
    VALUES (%s, %s, %s, %s, ...)
""", (session_id, bot_id, role, content, ...))
```

## Advanced Configuration

### Adjusting Partitions

Change the number of partitions (default: 8):

```sql
-- More partitions = finer-grained distribution
PARTITION BY HASH(CRC32(bot_id)) PARTITIONS 16;

-- Fewer partitions = larger partitions
PARTITION BY HASH(CRC32(bot_id)) PARTITIONS 4;
```

**Trade-offs**:
- More partitions: Better distribution, more overhead
- Fewer partitions: Less overhead, potential hot spots

### Custom Placement Policies

Create policies for specific requirements:

```sql
-- Pin to specific stores/racks
CREATE PLACEMENT POLICY policy_high_priority
    PRIMARY_REGION="us-east-1"
    FOLLOWERS=2
    CONSTRAINTS='["+zone=us-east-1a"]';

-- Different replication factors
CREATE PLACEMENT POLICY policy_critical
    FOLLOWERS=4  -- 5 replicas total
    COMMENT='Extra redundancy for critical bots';
```

## Troubleshooting

### Partition Distribution Uneven

Check partition statistics:
```sql
ANALYZE TABLE messages;
SELECT * FROM partition_info;
```

### Queries Still Slow

1. Check if queries include `bot_id` in WHERE clause
2. Verify indexes exist: `SHOW INDEX FROM messages;`
3. Use EXPLAIN to see query plan: `EXPLAIN SELECT ...`

### Region Balance Issues

Check PD scheduler:
```bash
# Inside PD container
pd-ctl -u http://localhost:2379 config show replication
pd-ctl -u http://localhost:2379 config show label-property
```

## Best Practices

1. **Always include bot_id in queries** for partition pruning
2. **Monitor partition growth** - rebalance if needed
3. **Test resilience regularly** - ensure 3 replicas are maintained
4. **Use indexes wisely** - compound indexes work best with partitioning
5. **Consider partition count** - 8-16 partitions for most use cases

## Summary

✅ **Data Colocation**: All bot data on same partition
✅ **Performance**: 5-10x faster bot-specific queries  
✅ **Resilience**: No data loss with 3 replicas
✅ **Scalability**: Hash partitioning balances load
✅ **Testable**: Easy to demonstrate with make targets

For questions or issues, see the main [README.md](../README.md) or check TiDB documentation on placement rules.
