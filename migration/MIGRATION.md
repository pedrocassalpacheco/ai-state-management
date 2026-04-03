# Migration Scripts

This folder contains scripts and configurations for CDC (Change Data Capture) replication between Aurora and TiDB.

## Architecture

```
Aurora RDS (Source)
    |
    | Binlog Stream
    v
DM Cluster (Docker Containers)
    ├── dm-master (coordinator)
    └── dm-worker (replicates data)
    |
    v
TiDB Cluster (Target - Docker Containers)
```

## CDC Replication Setup

Three sync modes are available:

1. **Incremental sync only** (`make sync-start`): Binlog replication only. Requires both databases to start in the same state.
2. **Full dump only** (`make sync-full`): One-time dump of all Aurora data. Stops after completion. Use to sync existing data once.
3. **Full dump + continuous sync** (`make sync-all`): Dumps all Aurora data, then continuously syncs changes via binlog. Use when starting fresh or databases are out of sync.

### Prerequisites

1. **Aurora RDS configured with binlog enabled and ROW format**:
   - Parameter: `binlog_format = ROW` (CRITICAL - MIXED/STATEMENT format will cause DM to skip INSERT/UPDATE events)
   - Enable binlog in Aurora cluster parameter group
   - Verify: `uv run python scripts/verify_binlog.py`
   
2. TiDB cluster running with DM containers (`make up`)

3. Environment variables in `.env`:
   - `AURORA_HOST`
   - `AURORA_USER`
   - `AURORA_PASSWORD`
   - `AURORA_PORT` (optional, defaults to 3306)

### Quick Start

**Option A: Incremental sync only (databases already match)**
```bash
# 1. Start TiDB cluster (includes DM containers)
make up

# 2. Start incremental CDC sync
make sync-start

# 3. Monitor replication
make sync-status

# 4. Stop sync when done
make sync-stop
```

**Option B: Full dump + continuous sync (starting fresh)**
```bash
# 1. Start TiDB cluster
make up

# 2. Reset TiDB to empty state
make reset-db-tidb

# 3. Start full dump + continuous sync
make sync-all

# 4. Monitor replication
make sync-status-all

# 5. Stop sync when done
make sync-stop-all
```

**Option C: One-time full dump (then incremental separately)**
```bash
# 1. Start TiDB cluster
make up

# 2. Reset TiDB to empty state
make reset-db-tidb

# 3. Run one-time full dump
make sync-full

# 4. Monitor dump progress
make sync-status-full

# 5. After dump completes, start incremental sync
make sync-start
```

### Available Commands

| Command | Description |
|---------|-------------|
| `make up` | Start TiDB cluster (includes dm-master and dm-worker) |
| **Incremental Sync** | |
| `make sync-start` | Start incremental CDC sync from Aurora to TiDB |
| `make sync-stop` | Stop incremental CDC sync |
| `make sync-status` | Check incremental CDC task status |
| **Full Dump Only** | |
| `make sync-full` | Run one-time full dump (stops after completion) |
| `make sync-status-full` | Check full dump task status |
| **Full Dump + Continuous Sync** | |
| `make sync-all` | Start full dump + continuous incremental sync |
| `make sync-stop-all` | Stop full + incremental sync task |
| `make sync-status-all` | Check full + incremental sync status |
| **Monitoring** | |
| `make sync-check` | Compare table row counts between Aurora and TiDB |

## How It Works

### Incremental Sync Only (`make sync-start`)

1. **Validates environment**: Checks .env for Aurora credentials
2. **Checks DM cluster**: Ensures dm-master and dm-worker are running
3. **Configures Aurora source**: Creates connection config for Aurora RDS
4. **Starts binlog replication**: Begins reading from current binlog position
5. **Applies changes to TiDB**: INSERT/UPDATE/DELETE operations synced in real-time

**When to use:** Both databases are already in the same state (same table counts).
**Task mode:** `incremental`
**Runs continuously:** Yes, until stopped

### Full Dump Only (`make sync-full`)

1. **Dumps Aurora data**: Uses mysqldump to export all existing data
2. **Loads into TiDB**: Imports the dump into TiDB
3. **Stops automatically**: Task completes and stops

**When to use:** Need to sync all existing data once, then manage incremental sync separately.
**Task mode:** `full`
**Runs continuously:** No, stops after dump completes

### Full Dump + Continuous Sync (`make sync-all`)

1. **Dumps Aurora data**: Uses mysqldump to export all existing data
2. **Loads into TiDB**: Imports the dump into TiDB
3. **Starts binlog replication**: Continues with incremental sync for new changes

**When to use:** Databases are not in sync, or you need to replicate all existing data.

**Note:** Full dump may take time depending on data size. Monitor with `dmctl query-status aurora-to-tidb-full`.

### Ongoing CDC Replication

Once `sync-start` completes:
- DM worker reads Aurora binlog continuously
- Applies INSERT/UPDATE/DELETE to TiDB in real-time
- Runs continuously in background
- Recovers from failures automatically

## Configuration Files

Located in `migration/` directory:

- **`dm-source-aurora.yaml`**: Aurora connection config (auto-generated from `.env`)
- **`dm-task-aurora-to-tidb.yaml`**: Incremental sync task definition (`task-mode: "incremental"`)
- **`dm-task-aurora-to-tidb-full.yaml`**: Full dump + incremental sync task definition (`task-mode: "all"`)
- **`cdc_sync.sh`**: Script to start incremental CDC sync
- **`cdc_full_sync.sh`**: Script to start full dump + incremental CDC sync

**Note:** The `dm-source-aurora.yaml` file is automatically generated from your `.env` file when you run `make sync-start`. This ensures your Aurora credentials are always up-to-date.

## Monitoring

```bash
# Check sync status
make sync-status

# Stop sync
make sync-stop
```

## Troubleshooting

### CDC not replicating data (synced: false, low totalEvents)

**Symptom:** `make sync-status` shows task running but `synced: false` and `totalEvents` stays very low while Aurora has active writes.

**Cause:** Aurora `binlog_format` is set to `MIXED` or `STATEMENT`. DM requires `ROW` format.

**Check:**
```bash
uv run python scripts/verify_binlog.py
```

**Fix:**
1. AWS Console → RDS → Parameter groups
2. Find your **DB Cluster Parameter Group** (Type: "DB Cluster Parameter Group")
   - If using default parameter group, create a new one first
3. Edit parameters → Search for `binlog_format`
4. Change value from `MIXED` to `ROW`
5. Save changes
6. Go to RDS → Databases → Select your Aurora cluster
7. Actions → **Reboot** (select "Reboot cluster")
   - ⚠️ **Cluster reboot is required** for parameter changes to take effect (1-2 min downtime)
   - The parameter will show "pending-reboot" status until you reboot
8. After reboot, verify: `make verify-binlog` (should show "ROW")
9. Restart CDC: `make sync-stop-all && make sync-all`

**Explanation:** In MIXED/STATEMENT mode, DM logs show `["ddl that dm doesn't handle, skip it"]` for INSERT/UPDATE statements, causing them to be skipped.

**Note:** Aurora requires cluster reboot for `binlog_format` changes. Session-level `SET SESSION binlog_format = 'ROW'` won't work for CDC since new connections won't inherit it.

### DM cluster not running
```bash
docker-compose ps dm-master dm-worker
docker-compose up -d dm-master dm-worker
```

### Check logs
```bash
docker-compose logs dm-master
docker-compose logs dm-worker
```

### Recreate task
```bash
make cdc-stop
make cdc-full
```

## Network Topology

All services run in `tidb-network` Docker network:
- Aurora: External (accessed via public IP/hostname)
- dm-master: Container (port 8261)
- dm-worker: Container (port 8262)
- TiDB: Container network (tidb0, tidb1, tidb2)

DM worker connects to:
- Aurora: Using credentials from .env
- TiDB: Using container hostname `tidb0:4000`
