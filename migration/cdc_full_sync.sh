#!/bin/bash
set -e

# Full CDC Sync: Dumps existing Aurora data, loads into TiDB, then starts incremental CDC
# This script handles task-mode: "all" for initial data synchronization

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_DIR="$PROJECT_ROOT/config"
TASK_CONFIG="$CONFIG_DIR/dm-task-aurora-to-tidb-full.yaml"

# DM control command wrapper (uses docker exec)
dmctl() {
    docker exec dm-master /dmctl --master-addr=dm-master:8261 "$@"
}

echo "Starting Full CDC Sync (Aurora -> TiDB)"
echo "========================================"

# Load environment variables
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "ERROR: .env file not found at $PROJECT_ROOT/.env"
    exit 1
fi

source "$PROJECT_ROOT/.env"

# Validate required environment variables
if [ -z "$AURORA_HOST" ] || [ -z "$AURORA_USER" ] || [ -z "$AURORA_PASSWORD" ]; then
    echo "ERROR: Missing required Aurora credentials in .env"
    echo "   Required: AURORA_HOST, AURORA_USER, AURORA_PASSWORD"
    exit 1
fi

# Check if DM cluster is running
echo "Checking DM cluster status..."
if ! docker ps --filter "name=dm-master" --filter "status=running" | grep -q dm-master; then
    echo "ERROR: DM cluster is not running. Please run 'docker-compose up -d dm-master dm-worker' first."
    exit 1
fi
echo "OK: DM cluster is running"

# Check if Aurora source is configured
echo "Checking Aurora data source..."
if ! dmctl operate-source show aurora-prod > /dev/null 2>&1; then
    echo "WARNING: Aurora source not configured. Creating now..."
    
    # Create Aurora source config if it doesn't exist
    SOURCE_CONFIG="$CONFIG_DIR/dm-source-aurora.yaml"
    if [ ! -f "$SOURCE_CONFIG" ]; then
        echo "Creating $SOURCE_CONFIG..."
        mkdir -p "$CONFIG_DIR"
        cat > "$SOURCE_CONFIG" <<EOF
# Aurora RDS MySQL Source Configuration
source-id: "aurora-prod"
enable-gtid: false
enable-relay: true
relay-dir: "/data/relay"

from:
  host: "$AURORA_HOST"
  user: "$AURORA_USER"
  password: "$AURORA_PASSWORD"
  port: ${AURORA_PORT:-3306}
EOF
    fi
    
    dmctl operate-source create /config/dm-source-aurora.yaml
    echo "OK: Aurora source configured"
else
    echo "OK: Aurora source already configured"
fi

# Create full sync task configuration
echo "Creating full sync task configuration..."
mkdir -p "$CONFIG_DIR"

cat > "$TASK_CONFIG" <<EOF
# Full CDC Sync Task Configuration
# This performs: full dump -> load -> incremental CDC
name: "aurora-to-tidb-full"
task-mode: "all"

# Ignore validation checks that fail with Aurora MySQL 8.4+
ignore-checking-items: ["all"]

target-database:
  host: "tidb0"
  port: 4000
  user: "root"
  password: ""

block-allow-list:
  ai-db-allowlist:
    do-dbs: ["ai_state_management"]

mysql-instances:
  - source-id: "aurora-prod"
    block-allow-list: "ai-db-allowlist"
    syncer-config-name: "global"

syncers:
  global:
    worker-count: 16
    batch: 100
    max-retry: 100
    multiple-rows: true

clean-dump-file: true
collation_compatible: "loose"
EOF

echo "OK: Created $TASK_CONFIG"

# Skip validation - Aurora MySQL 8.4+ has compatibility issues with DM checks
echo "Skipping validation (Aurora MySQL 8.4+ not fully compatible with DM checks)"
echo "Task will fail at runtime if there are real issues"

# Check if TiDB is accessible from DM worker
echo "Checking TiDB connectivity..."
if ! docker exec dm-worker mysqlsh --uri="root@tidb0:4000" --sql -e "SELECT 1" > /dev/null 2>&1; then
    echo "ERROR: Cannot connect to TiDB from DM worker"
    echo "Trying alternative check..."
    if docker exec dm-master mysqlsh --uri="root@tidb0:4000" --sql -e "SELECT 1" > /dev/null 2>&1; then
        echo "OK: TiDB is accessible from dm-master"
    else
        echo "WARNING: Cannot verify TiDB connectivity, continuing anyway..."
    fi
else
    echo "OK: TiDB is accessible"
fi

# Warn about existing data
echo ""
echo "WARNING: Full sync will:"
echo "   1. Drop and recreate target tables in TiDB"
echo "   2. Dump all data from Aurora's ai_state_management database"
echo "   3. Load data into TiDB"
echo "   4. Start incremental CDC replication"
echo ""
read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "ERROR: Cancelled by user"
    exit 1
fi

# Start full sync task
echo ""
echo "Starting full sync task..."
echo "   This may take several minutes depending on data size..."
echo ""

if ! dmctl start-task /config/dm-task-aurora-to-tidb-full.yaml; then
    echo "ERROR: Failed to start full sync task"
    echo "Checking task status..."
    dmctl query-status aurora-to-tidb-full || true
    exit 1
fi

echo ""
echo "OK: Full sync task started successfully!"
echo ""
echo "Monitor progress with:"
echo "   make cdc-status"
echo ""
echo "The task will:"
echo "   1. Dump: Export Aurora data (check worker logs)"
echo "   2. Load: Import to TiDB (may take time)"
echo "   3. Sync: Start incremental CDC (ongoing)"
echo ""
