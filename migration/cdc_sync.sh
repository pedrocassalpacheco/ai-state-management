#!/bin/bash
set -e

# CDC Sync: Start a TiDB DM replication task from Aurora to TiDB
# Usage: cdc_sync.sh <mode>
#   incremental  - Binlog sync only (databases must already be in sync)
#   full         - One-time full data dump, then stops
#   all          - Full dump + continuous incremental sync

MODE="${1:-incremental}"

case "$MODE" in
    incremental)
        TASK_NAME="aurora-to-tidb-cdc"
        TASK_FILE="dm-task-aurora-to-tidb.yaml"
        DESCRIPTION="Incremental CDC Sync (binlog only)"
        ;;
    full)
        TASK_NAME="aurora-to-tidb-full"
        TASK_FILE="dm-task-aurora-to-tidb-full.yaml"
        DESCRIPTION="Full Dump (one-time, stops when complete)"
        ;;
    all)
        TASK_NAME="aurora-to-tidb-all"
        TASK_FILE="dm-task-aurora-to-tidb-all.yaml"
        DESCRIPTION="Full Dump + Continuous Incremental Sync"
        ;;
    *)
        echo "ERROR: Unknown mode '$MODE'"
        echo "Usage: $0 <incremental|full|all>"
        exit 1
        ;;
esac

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# DM control command wrapper (uses docker exec)
dmctl() {
    docker exec dm-master /dmctl --master-addr=dm-master:8261 "$@"
}

echo "Starting $DESCRIPTION (Aurora -> TiDB)"
echo "$(echo "Starting $DESCRIPTION (Aurora -> TiDB)" | tr '[:print:]' '=')"

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
    echo "ERROR: DM cluster is not running. Please start it with 'make up' first."
    exit 1
fi
echo "✓ DM cluster is running"

# Generate dm-source-aurora.yaml from environment variables
SOURCE_CONFIG="$SCRIPT_DIR/dm-source-aurora.yaml"
echo "Generating Aurora source config from .env..."

cat > "$SOURCE_CONFIG" <<EOF
# Aurora RDS MySQL Source Configuration (auto-generated)
source-id: "aurora-prod"
enable-gtid: false
enable-relay: false

from:
  host: "$AURORA_HOST"
  user: "$AURORA_USER"
  password: "$AURORA_PASSWORD"
  port: ${AURORA_PORT:-3306}
EOF

# Configure Aurora source - try to create, skip if already exists
# NOTE: Never stop the source, as that would kill any running tasks
echo "Checking Aurora data source..."
create_output=$(dmctl operate-source create /migration/dm-source-aurora.yaml 2>&1)
if echo "$create_output" | grep -q '"result": true'; then
    echo "✓ Aurora source created"
elif echo "$create_output" | grep -q 'already exists'; then
    echo "✓ Aurora source already configured"
else
    echo "ERROR: Failed to configure Aurora source:"
    echo "$create_output"
    exit 1
fi

# Check if task is already running
echo "Checking for existing task '$TASK_NAME'..."
task_status=$(dmctl query-status "$TASK_NAME" 2>&1)

if echo "$task_status" | grep -q '"stage"'; then
    echo "✓ Task '$TASK_NAME' is already running"
    echo ""
    echo "$task_status" | head -20
    exit 0
fi

# Start task
# Use --remove-meta for full/all modes to clear stale checkpoints from previous runs
echo ""
echo "Starting task '$TASK_NAME'..."
echo ""

START_FLAGS=""
[ "$MODE" != "incremental" ] && START_FLAGS="--remove-meta"

if ! dmctl start-task $START_FLAGS "/migration/$TASK_FILE"; then
    echo "ERROR: Failed to start task"
    dmctl query-status "$TASK_NAME" || true
    exit 1
fi

echo ""
echo "✓ Task '$TASK_NAME' started successfully!"
echo ""
echo "Monitor with: make sync-status$([ "$MODE" = "incremental" ] && echo "" || echo "-$MODE")"
[ "$MODE" != "full" ] && echo "Stop with:    make sync-stop$([ "$MODE" = "incremental" ] && echo "" || echo "-$MODE")"
[ "$MODE" = "full" ] && echo "Note: Task will stop automatically when dump completes."
echo ""

