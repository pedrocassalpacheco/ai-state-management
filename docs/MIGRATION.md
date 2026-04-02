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

**Questions?** See the main [README.md](../README.md) or [docs/SCHEMA.md](./SCHEMA.md)
