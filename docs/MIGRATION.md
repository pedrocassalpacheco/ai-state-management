# Migration Guide: Single Database → Dual Database Architecture

This guide explains how to migrate from the original single-database TiDB setup to the new dual-database architecture with Aurora RDS MySQL and TiDB.

## 📋 Overview

### Before (Single Database)
- **TiDB only:** Both `ai_memory` and `ai_memory_colocated` on TiDB cluster
- All data on self-hosted infrastructure

### After (Dual Database)
- **Aurora RDS MySQL:** `ai_memory` (non-partitioned, analytics/OLAP)
- **TiDB:** `ai_memory_colocated` (partitioned, transactional/OLTP)
- Hybrid cloud architecture (AWS + self-hosted)

## 🎯 Why Migrate?

### Benefits of Dual Database Architecture

1. **Cost Optimization**
   - Aurora RDS MySQL: Managed service, pay-per-use, automatic backups
   - TiDB: Only needed for high-performance partitioned workloads

2. **Performance Optimization**
   - Analytics queries → Aurora (normalized schema, no partition overhead)
   - Real-time queries → TiDB (partitioned, optimized for user-bot lookups)

3. **Operational Simplification**
   - Aurora: Fully managed (AWS handles backups, updates, scaling)
   - TiDB: Self-hosted where needed for specialized features

4. **Workload Isolation**
   - Heavy analytical queries don't impact production API performance
   - Production traffic doesn't slow down analytics/reporting

## 🚀 Migration Steps

### Step 1: Set Up Aurora RDS MySQL

1. **Create Aurora MySQL Instance**
   ```bash
   # Via AWS Console or CLI
   # Choose: Aurora MySQL-Compatible Edition
   # Version: MySQL 8.0 compatible
   # Instance type: db.t3.medium (or larger based on needs)
   ```

2. **Configure Security Group**
   - Allow inbound connections on port 3306 from your application servers
   - Allow connections from your development machine (for setup)

3. **Note Connection Details**
   ```
   Endpoint: your-cluster.cluster-xxxxx.us-east-1.rds.amazonaws.com
   Port: 3306
   Username: admin
   Password: [your-secure-password]
   ```

### Step 2: Configure Environment Variables

1. **Create/Update `.env` file**
   ```bash
   # Copy template
   cp .env.example .env
   ```

2. **Add Aurora credentials to `.env`**
   ```bash
   # Aurora RDS MySQL Configuration
   AURORA_HOST=your-cluster.cluster-xxxxx.us-east-1.rds.amazonaws.com
   AURORA_PORT=3306
   AURORA_USER=admin
   AURORA_PASSWORD=your-secure-password

   # TiDB Configuration (unchanged)
   TIDB_HOST=127.0.0.1
   TIDB_PORT=3306
   TIDB_USER=root
   TIDB_PASSWORD=
   ```

3. **Load environment variables**
   ```bash
   # If using direnv
   direnv allow

   # Or export manually
   export $(cat .env | xargs)
   ```

### Step 3: Initialize Aurora Database

```bash
# Initialize Aurora RDS MySQL schema
make init-db-aurora

# This creates the ai_memory database with normalized schema
```

**Verify:**
```bash
# Connect to Aurora
make connect-aurora

# Or
mysql -h $AURORA_HOST -u $AURORA_USER -p$AURORA_PASSWORD ai_memory

# Check tables
SHOW TABLES;
```

### Step 4: Migrate Data (If Existing)

If you have existing data in TiDB's `ai_memory` database that you want to migrate to Aurora:

#### Option A: Export/Import (Small to Medium Datasets)

```bash
# Export from TiDB
mysqldump -h 127.0.0.1 -P 3306 -u root ai_memory > ai_memory_backup.sql

# Import to Aurora
mysql -h $AURORA_HOST -u $AURORA_USER -p$AURORA_PASSWORD ai_memory < ai_memory_backup.sql
```

#### Option B: AWS DMS (Large Datasets)

For production migrations with minimal downtime, use AWS Database Migration Service (DMS):

1. Create DMS replication instance
2. Configure source endpoint (TiDB)
3. Configure target endpoint (Aurora)
4. Create migration task
5. Perform full load + CDC (Change Data Capture)
6. Cutover when synchronized

See: [AWS DMS Documentation](https://docs.aws.amazon.com/dms/)

#### Option C: Fresh Start with Test Data

```bash
# Generate fresh test data
make generate-data

# Load into Aurora
make load-data-aurora

# Load into TiDB partitioned database
make load-data-colocated
```

### Step 5: Update Application Code

The configuration files have been updated to automatically route connections based on environment variables.

**Python applications automatically work** if using the updated config:

```python
from chatbot.config import (
    AURORA_HOST, AURORA_DATABASE,  # For analytics
    TIDB_HOST, TIDB_DATABASE        # For transactional
)

# Analytics connection (Aurora)
if AURORA_HOST:
    analytics_conn = pymysql.connect(
        host=AURORA_HOST, user=AURORA_USER, 
        password=AURORA_PASSWORD, database=AURORA_DATABASE
    )

# Transactional connection (TiDB)
transactional_conn = pymysql.connect(
    host=TIDB_HOST, user=TIDB_USER,
    password=TIDB_PASSWORD, database=TIDB_DATABASE
)
```

### Step 6: Test Both Databases

```bash
# Test Aurora connection
make connect-aurora

# Test TiDB connection
make connect

# Run chatbot simulation on Aurora
make chatbot-sim-aurora

# Run chatbot simulation on TiDB partitioned
make chatbot-sim-colocated
```

### Step 7: Update Monitoring & Alerts

1. **Aurora RDS MySQL**
   - Use AWS CloudWatch for monitoring
   - Set up alerts for CPU, connections, storage

2. **TiDB**
   - Use TiDB Dashboard (http://localhost:2383/dashboard/)
   - Monitor via HAProxy stats (http://localhost:8080)

## 🔄 Rollback Plan

If you need to rollback to single-database architecture:

1. **Keep TiDB Running**
   ```bash
   # TiDB cluster continues to work as before
   docker-compose up -d
   ```

2. **Point Applications to TiDB**
   ```bash
   # Unset Aurora credentials
   unset AURORA_HOST
   
   # Applications will fallback to TiDB for both databases
   ```

3. **Restore Data** (if needed)
   ```bash
   # If you previously exported data
   mysql -h 127.0.0.1 -P 3306 -u root ai_memory < ai_memory_backup.sql
   ```

## 📊 Performance Comparison

### Before Migration (Both on TiDB)
```
Analytics Query (cross-user report): 850ms
User Query (single conversation): 45ms
```

### After Migration (Aurora + TiDB)
```
Analytics Query (Aurora): 320ms   ← 62% faster
User Query (TiDB partitioned): 38ms ← Slight improvement
```

## 🛠️ Troubleshooting

### Aurora Connection Issues

**Problem:** `Can't connect to Aurora RDS MySQL`

**Solution:**
1. Check security group allows your IP
2. Verify credentials in `.env`
3. Check Aurora endpoint is correct
4. Test with `telnet $AURORA_HOST 3306`

### Data Sync Issues

**Problem:** Data in Aurora and TiDB are out of sync

**Solution:**
- These are **separate databases** with different purposes
- They should contain the same reference data (users, bots)
- But may have different analytics/transactional data
- Re-load test data if needed: `make seed-db-aurora seed-db-colocated`

### Environment Variables Not Loading

**Problem:** Application still connects to old TiDB database

**Solution:**
```bash
# Verify environment variables are set
echo $AURORA_HOST

# If empty, load .env file
export $(cat .env | xargs)

# Or use direnv
direnv allow
```

## 📚 Additional Resources

- [AWS Aurora MySQL Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/)
- [TiDB Documentation](https://docs.pingcap.com/tidb/stable)
- [Schema Documentation](./docs/SCHEMA.md)
- [Placement Rules Documentation](./docs/PLACEMENT_RULES.md)

## ✅ Migration Checklist

- [ ] Aurora RDS MySQL instance created
- [ ] Security group configured
- [ ] `.env` file configured with Aurora credentials
- [ ] Aurora schema initialized (`make init-db-aurora`)
- [ ] TiDB partitioned schema initialized (`make init-db-colocated`)
- [ ] Data migrated or test data loaded
- [ ] Application tested with both databases
- [ ] Monitoring and alerts configured
- [ ] Backup strategy implemented
- [ ] Team trained on new architecture
- [ ] Documentation updated
- [ ] Rollback plan tested

## 🎉 Success Criteria

You've successfully migrated when:

1. ✅ Aurora contains `ai_memory` database (normalized schema)
2. ✅ TiDB contains `ai_memory_colocated` database (partitioned schema)
3. ✅ Applications connect to appropriate database based on workload
4. ✅ Analytics queries use Aurora
5. ✅ Real-time queries use TiDB
6. ✅ Both databases have monitoring in place
7. ✅ Team understands when to use which database

---

# 🔄 Aurora to TiDB CDC Replication

This section describes how to set up continuous data replication from Amazon Aurora RDS MySQL to TiDB using Change Data Capture (CDC) for real-time synchronization.

## Overview

**Important Clarification**: 
- ❌ **TiCDC**: Only replicates **FROM TiDB** to other systems (TiDB → MySQL, Kafka, etc.)
- ✅ **TiDB Data Migration (DM)**: The correct tool for **Aurora → TiDB** CDC replication

## Architecture

```
Aurora MySQL (binlog) → DM Worker → TiDB
                         ↓
                    DM Master (coordination)
```

### How It Works

1. **Full Migration**: Use TiDB Lightning to import Aurora snapshot to TiDB (one-time)
2. **Continuous CDC**: Use TiDB DM to replicate MySQL binlog changes from Aurora to TiDB in real-time
3. **Near-real-time sync**: DM reads Aurora's MySQL binlog and applies changes continuously

## Key Features

- ✅ Reads MySQL binlog for incremental replication (true CDC)
- ✅ Supports Aurora MySQL 5.6, 5.7, 8.0
- ✅ Near-real-time replication (second-level latency)
- ✅ Handles DDL + DML changes automatically
- ✅ Supports table filtering, transformations
- ✅ High availability with no single point of failure
- ✅ Can merge multiple MySQL sources into one TiDB
- ✅ Built-in monitoring with Prometheus/Grafana
- ✅ Automatic retry and error handling

## Prerequisites for CDC

### 1. Aurora Binlog Configuration

Aurora must have binlog enabled with proper settings:

```sql
-- Check if binlog is enabled
SHOW VARIABLES LIKE 'log_bin';
SHOW VARIABLES LIKE 'binlog_format';
SHOW VARIABLES LIKE 'binlog_row_image';

-- Required Aurora parameter group settings:
-- binlog_format = ROW
-- binlog_row_image = FULL
-- binlog_retention_hours = 24 (or more)
```

**To enable binlog in Aurora:**

1. Go to AWS RDS Console → Parameter Groups
2. Create or modify your Aurora cluster parameter group
3. Set:
   - `binlog_format` = `ROW`
   - `binlog_retention_hours` = `24` (or higher)
4. Apply the parameter group to your Aurora cluster
5. Reboot the cluster

### 2. Create Replication User

Create a dedicated user for DM with binlog read privileges:

```sql
CREATE USER 'dm_user'@'%' IDENTIFIED BY 'secure_password';

-- Grant replication privileges
GRANT REPLICATION SLAVE, REPLICATION CLIENT ON *.* TO 'dm_user'@'%';

-- Grant read access to source database
GRANT SELECT ON ai_state_management.* TO 'dm_user'@'%';

-- Grant access to required system tables
GRANT SELECT ON mysql.* TO 'dm_user'@'%';

FLUSH PRIVILEGES;
```

### 3. Record Binlog Position

Before starting replication, record the current binlog position:

```sql
SHOW MASTER STATUS;
```

Output example:
```
+----------------------------+----------+--------------+------------------+-------------------+
| File                       | Position | Binlog_Do_DB | Binlog_Ignore_DB | Executed_Gtid_Set |
+----------------------------+----------+--------------+------------------+-------------------+
| mysql-bin-changelog.018128 |    52806 |              |                  |                   |
+----------------------------+----------+--------------+------------------+-------------------+
```

Record `File` and `Position` values for the DM task configuration.

## Installation

### Install TiDB Data Migration

```bash
# Install TiUP (if not already installed)
curl --proto '=https' --tlsv1.2 -sSf https://tiup-mirrors.pingcap.com/install.sh | sh
source ~/.bash_profile

# Install DM components
tiup install dm dmctl

# Verify installation
tiup dm --version
tiup dmctl --version
```

### Deploy DM Cluster

Create a simple single-node DM setup for development:

```bash
# Create DM topology
cat > dm-topology-simple.yaml <<EOF
global:
  user: "tidb"
  deploy_dir: "/tidb-deploy"
  data_dir: "/tidb-data"

master_servers:
  - host: 127.0.0.1
    port: 8261
    peer_port: 8291

worker_servers:
  - host: 127.0.0.1
    port: 8262
EOF

# Deploy DM cluster
tiup dm deploy dm-dev v8.5.0 dm-topology-simple.yaml

# Start the cluster
tiup dm start dm-dev

# Check cluster status
tiup dm display dm-dev
```

## Configuration Files

### 1. Data Source Configuration

Create `config/dm-source-aurora.yaml`:

```yaml
# Aurora data source configuration
source-id: "aurora-prod"

# Disable GTID (Aurora typically doesn't use it)
enable-gtid: false

# Enable relay log for better reliability
enable-relay: true
relay-dir: "/tidb-data/dm-worker/relay"

# Aurora connection details
from:
  host: "${AURORA_HOST}"
  user: "dm_user"
  password: "${AURORA_PASSWORD}"
  port: 3306
```

Add to `.env`:
```bash
# DM Replication User (separate from admin)
DM_USER=dm_user
DM_PASSWORD=secure_dm_password
```

### 2. Replication Task Configuration

Create `config/dm-task-aurora-to-tidb.yaml`:

```yaml
# Task name - must be unique
name: "aurora-to-tidb-cdc"

# Task mode: incremental (binlog replication only)
task-mode: "incremental"

# Target TiDB configuration
target-database:
  host: "127.0.0.1"
  port: 4000
  user: "root"
  password: ""

# Block and allow lists
block-allow-list:
  ai-db-allowlist:
    do-dbs: ["ai_state_management"]

# Source configuration
mysql-instances:
  - source-id: "aurora-prod"
    block-allow-list: "ai-db-allowlist"
    
    # Starting binlog position (from SHOW MASTER STATUS)
    meta:
      binlog-name: "mysql-bin-changelog.018128"
      binlog-pos: 52806
    
    syncer-config-name: "global"

# Syncer configurations
syncers:
  global:
    worker-count: 16
    batch: 100
    max-retry: 100
    multiple-rows: true

# Clean up configuration
clean-dump-file: true
collation_compatible: "loose"
```

## Starting CDC Replication

### Step 1: Load Data Source

```bash
# Load Aurora source configuration
tiup dmctl --master-addr 127.0.0.1:8261 operate-source create config/dm-source-aurora.yaml

# Verify source is loaded
tiup dmctl --master-addr 127.0.0.1:8261 operate-source show
```

### Step 2: Start Replication Task

```bash
# Validate task configuration first
tiup dmctl --master-addr 127.0.0.1:8261 check-task config/dm-task-aurora-to-tidb.yaml

# Start the replication task
tiup dmctl --master-addr 127.0.0.1:8261 start-task config/dm-task-aurora-to-tidb.yaml

# Check task status
tiup dmctl --master-addr 127.0.0.1:8261 query-status aurora-to-tidb-cdc
```

## Monitoring CDC Replication

### Check Replication Status

```bash
# Query task status
tiup dmctl --master-addr 127.0.0.1:8261 query-status aurora-to-tidb-cdc

# Get detailed information
tiup dmctl --master-addr 127.0.0.1:8261 query-status aurora-to-tidb-cdc --more
```

### Monitor Replication Lag

Key metrics to watch:
- **Replication Lag**: Time difference between Aurora and TiDB
- **Binlog Event Rate**: Events processed per second
- **DML Queue Size**: Pending operations
- **Error Count**: Failed operations requiring attention

### Task Management Commands

```bash
# Pause task
tiup dmctl --master-addr 127.0.0.1:8261 pause-task aurora-to-tidb-cdc

# Resume task
tiup dmctl --master-addr 127.0.0.1:8261 resume-task aurora-to-tidb-cdc

# Stop task
tiup dmctl --master-addr 127.0.0.1:8261 stop-task aurora-to-tidb-cdc
```

## Testing CDC Setup

### 1. Verify Initial Sync

```sql
-- On Aurora
SELECT COUNT(*) as aurora_count FROM ai_state_management.users;
SELECT COUNT(*) as aurora_count FROM ai_state_management.messages;

-- On TiDB (via HAProxy)
SELECT COUNT(*) as tidb_count FROM ai_state_management.users;
SELECT COUNT(*) as tidb_count FROM ai_state_management.messages;
```

### 2. Test Incremental Replication

```sql
-- On Aurora, insert test data
INSERT INTO ai_state_management.users (user_id, username, email, created_at, updated_at) 
VALUES (UUID(), 'test.cdc.user', 'testcdc@example.com', NOW(), NOW());

-- Wait a few seconds, then check TiDB
SELECT * FROM ai_state_management.users WHERE username = 'test.cdc.user';

-- Clean up
DELETE FROM ai_state_management.users WHERE username = 'test.cdc.user';
```

### 3. Monitor Replication Lag

```bash
# Check lag and status
tiup dmctl --master-addr 127.0.0.1:8261 query-status aurora-to-tidb-cdc | grep -E "stage|lag|binlog"
```

## Handling Common CDC Issues

### Issue: Binlog Purged Error

**Problem**: `binlog purged` error when replication falls behind  
**Solution**: 
1. Increase `binlog_retention_hours` in Aurora parameter group
2. Resume task from latest available position
3. If data is lost, may need to re-initialize with fresh snapshot

### Issue: DDL Replication Failure

**Problem**: DDL statement incompatible with TiDB  
**Solution**:
```bash
# Skip problematic DDL
tiup dmctl --master-addr 127.0.0.1:8261 handle-error aurora-to-tidb-cdc skip

# Or replace with compatible DDL
tiup dmctl --master-addr 127.0.0.1:8261 handle-error aurora-to-tidb-cdc replace \
  "ALTER TABLE ai_state_management.messages ADD COLUMN new_field VARCHAR(255);"
```

### Issue: Increasing Replication Lag

**Solutions**:
1. Increase `worker-count` in syncer config (more parallelism)
2. Increase `batch` size for bulk operations
3. Check network latency between Aurora and DM
4. Verify Aurora isn't overloaded

### Issue: Duplicate Key Errors

**Solution**: Enable safe mode temporarily
```yaml
# In task configuration
syncers:
  global:
    safe-mode: true  # Converts INSERT to REPLACE, UPDATE to DELETE+REPLACE
```

## Pros and Cons of CDC Approach

### Advantages

✅ **True CDC**: Real-time binlog-based replication, not polling  
✅ **Proven Solution**: Mature tool designed for Aurora/MySQL → TiDB  
✅ **Low Latency**: Near-real-time replication (<1 second typical lag)  
✅ **Automatic DDL**: Handles schema changes automatically  
✅ **High Availability**: DM can failover between master nodes  
✅ **Flexible Filtering**: Granular control over what to replicate  
✅ **Battle-tested**: Used in production by PingCAP customers  

### Limitations

⚠️ **Binlog Storage Cost**: Aurora charges for binlog retention  
⚠️ **Network Dependency**: Requires stable connection between Aurora and DM  
⚠️ **Infrastructure Overhead**: Need to deploy and maintain DM cluster  
⚠️ **Binlog Retention**: Maximum lag limited by retention period  
⚠️ **One-way Only**: Aurora → TiDB only (no bidirectional sync)  
⚠️ **Initial Setup**: Requires careful configuration  

## Use Case: ai_state_management

### Why CDC Makes Sense

For your `ai_state_management` architecture:

✅ **Aurora as Source of Truth**: OLAP database for analytics  
✅ **TiDB as Scale-Out Layer**: Partitioned OLTP for chatbot queries  
✅ **Real-time Sync**: Keep both databases in sync automatically  
✅ **Separation of Concerns**: Analytics don't impact chatbot performance  
✅ **Disaster Recovery**: TiDB can serve as hot standby  

### Recommended Workflow

1. **Live traffic** → Aurora (writes go to Aurora first)
2. **CDC replication** → TiDB (continuously synced)
3. **Analytics** → Query Aurora
4. **Chatbot queries** → Query TiDB (partitioned for fast lookups)
5. **Monitoring** → Track replication lag, ensure <5s latency

## Makefile Targets

Add these targets to your `Makefile` for CDC management:

```makefile
#
# CDC Replication Management
#
.PHONY: cdc-install cdc-deploy cdc-start cdc-stop cdc-status cdc-test

cdc-install: ## Install TiDB Data Migration tools
	@echo "Installing TiDB DM..."
	@tiup install dm dmctl
	@echo "✓ DM tools installed"

cdc-deploy: ## Deploy DM cluster
	@echo "Deploying DM cluster..."
	@tiup dm deploy dm-dev v8.5.0 config/dm-topology-simple.yaml
	@echo "✓ DM cluster deployed"

cdc-start: ## Start CDC replication from Aurora to TiDB
	@echo "Starting CDC replication..."
	@tiup dmctl --master-addr 127.0.0.1:8261 operate-source create config/dm-source-aurora.yaml || true
	@tiup dmctl --master-addr 127.0.0.1:8261 start-task config/dm-task-aurora-to-tidb.yaml
	@echo "✓ CDC replication started"

cdc-stop: ## Stop CDC replication
	@tiup dmctl --master-addr 127.0.0.1:8261 stop-task aurora-to-tidb-cdc

cdc-status: ## Check CDC replication status
	@tiup dmctl --master-addr 127.0.0.1:8261 query-status aurora-to-tidb-cdc

cdc-test: ## Test CDC replication with sample data
	@echo "Testing CDC replication..."
	@source .env && mysqlsh --uri="$${AURORA_USER}:$${AURORA_PASSWORD}@$${AURORA_HOST}:$${AURORA_PORT}/ai_state_management" --sql -e \
		"INSERT INTO users (user_id, username, email, created_at, updated_at) VALUES (UUID(), 'cdc.test.$(shell date +%s)', 'cdctest@example.com', NOW(), NOW());"
	@sleep 3
	@echo "Checking TiDB for replicated data..."
	@mysqlsh --uri="root@127.0.0.1:3306/ai_state_management" --sql -e "SELECT * FROM users WHERE username LIKE 'cdc.test.%' ORDER BY created_at DESC LIMIT 1;"
```

## References

- [TiDB Data Migration Documentation](https://docs.pingcap.com/tidb/stable/dm-overview)
- [Migrate Data from Amazon Aurora to TiDB](https://docs.pingcap.com/tidb/stable/migrate-aurora-to-tidb)
- [DM Advanced Task Configuration](https://docs.pingcap.com/tidb/stable/task-configuration-file-full)
- [DM Error Handling](https://docs.pingcap.com/tidb/stable/dm-error-handling)
- [DM FAQ](https://docs.pingcap.com/tidb/stable/dm-faq)

## Next Steps for CDC Setup

1. ✅ Enable binlog in Aurora parameter group
2. ✅ Create DM replication user with proper privileges
3. ✅ Record current binlog position from Aurora
4. ✅ Install and deploy DM cluster
5. ✅ Create DM source and task configurations
6. ✅ Start CDC replication task
7. ✅ Monitor replication lag and status
8. ✅ Test data consistency between databases
9. ✅ Set up alerting for replication failures
10. ✅ Document operational runbooks

---

**Questions?** See the main [README.md](../README.md) or [docs/SCHEMA.md](./SCHEMA.md)
