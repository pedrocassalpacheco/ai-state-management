# Migration Scripts

This folder contains scripts and configurations for data migration and CDC replication between Aurora and TiDB.

## Architecture

```
Aurora RDS (OLAP)
    |
    | Binlog Stream
    v
DM Cluster (Docker Containers)
    ├── dm-master (coordinator)
    └── dm-worker (replicates data)
    |
    v
TiDB Cluster (OLTP - Docker Containers)
```

## CDC Replication Setup

### Prerequisites

1. Aurora RDS configured with binlog enabled
2. TiDB cluster running (`make up`)
3. Environment variables in `.env`:
   - `AURORA_HOST`
   - `AURORA_USER`
   - `AURORA_PASSWORD`
   - `AURORA_PORT` (optional, defaults to 3306)

### Quick Start

```bash
# 1. Start DM cluster
make cdc-deploy

# 2. Check Aurora binlog status
make cdc-binlog

# 3. Run full sync (initial load + CDC)
make cdc-full

# 4. Monitor replication
make cdc-status
```

### Available Commands

| Command | Description |
|---------|-------------|
| `make cdc-deploy` | Deploy DM master and worker containers |
| `make cdc-binlog` | Check Aurora binlog configuration and position |
| `make cdc-full` | Full sync: dump existing data + start CDC |
| `make cdc-status` | Check replication status |
| `make cdc-pause` | Pause CDC replication |
| `make cdc-resume` | Resume CDC replication |
| `make cdc-stop` | Stop CDC task |
| `make cdc-logs` | View DM worker logs |
| `make cdc-test` | Test replication with sample insert |

## How It Works

### Initial Full Sync (`make cdc-full`)

1. **Validates environment**: Checks .env for Aurora credentials
2. **Checks DM cluster**: Ensures dm-master and dm-worker are running
3. **Configures Aurora source**: Creates connection config for Aurora
4. **Creates task config**: Generates YAML with `task-mode: "all"`
5. **Full dump**: Exports all Aurora tables
6. **Load to TiDB**: Imports data into TiDB
7. **Switches to CDC**: Automatically starts incremental replication

### Ongoing CDC Replication

Once `cdc-full` completes:
- DM worker reads Aurora binlog
- Applies INSERT/UPDATE/DELETE to TiDB
- Runs continuously in background
- Recovers from failures automatically

## Configuration Files

Generated in `config/` directory:

- `dm-source-aurora.yaml`: Aurora connection config
- `dm-task-aurora-to-tidb-full.yaml`: Full sync task definition

## Monitoring

```bash
# Check status
make cdc-status

# View worker logs
make cdc-logs

# Test replication
make cdc-test
```

## Troubleshooting

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
