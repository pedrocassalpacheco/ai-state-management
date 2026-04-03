#!/bin/bash
set -e

# Full Dump (One-time): Dumps all Aurora data to TiDB and stops
# Does NOT start incremental sync - use 'make sync-start' afterwards if needed

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_DIR="$SCRIPT_DIR"
TASK_CONFIG="$CONFIG_DIR/dm-task-aurora-to-tidb-full.yaml"

# DM control command wrapper (uses docker exec)
dmctl() {
    docker exec dm-master /dmctl --master-addr=dm-master:8261 "$@"
}

echo "Starting Full Dump (Aurora -> TiDB)"
echo "===================================="
echo "One-time dump: Will export all Aurora data and stop"
echo ""

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
    echo "ERROR: DM cluster is not running. Please run 'make cdc-deploy' first."
    exit 1
fi
echo "✓ DM cluster is running"

# Generate dm-source-aurora.yaml from environment variables
SOURCE_CONFIG="$CONFIG_DIR/dm-source-aurora.yaml"
echo "Generating $SOURCE_CONFIG from .env..."

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

# Check if Aurora source is configured
echo "Checking Aurora data source..."
if dmctl operate-source show aurora-prod 2>&1 | grep -q '"aurora-prod"'; then
    echo "Aurora source already exists, updating..."
    dmctl operate-source stop aurora-prod > /dev/null 2>&1 || true
    dmctl operate-source create /migration/dm-source-aurora.yaml
else
    echo "Creating new Aurora source..."
    dmctl operate-source create /migration/dm-source-aurora.yaml
fi
echo "✓ Aurora source configured"

# Check if task is already running
echo "Checking for existing CDC task..."
task_status=$(dmctl query-status aurora-to-tidb-full 2>&1)

if echo "$task_status" | grep -q '"stage"'; then
    echo "WARNING: CDC task 'aurora-to-tidb-full' is already running"
    echo ""
    echo "$task_status" | head -20
    exit 0
fi

# Start full dump task (one-time)
echo ""
echo "Starting full dump task..."
echo "   Step 1: Dumping all data from Aurora..."
echo "   Step 2: Loading data into TiDB..."
echo "   Task will stop automatically when dump completes"
echo ""

if ! dmctl start-task /migration/dm-task-aurora-to-tidb-full.yaml; then
    echo "ERROR: Failed to start CDC task"
    echo "Checking task status..."
    dmctl query-status aurora-to-tidb-full || true
    exit 1
fi

echo ""
echo "✓ Full dump task started successfully!"
echo ""
echo "The task will:"
echo "  1. Dump all existing data from Aurora (this may take time)"
echo "  2. Load the data into TiDB"
echo "  3. Stop automatically when complete"
echo ""
echo "Note: This is a one-time dump. For continuous sync, run 'make sync-start' after."
echo ""
echo "Monitor with: docker exec dm-master /dmctl --master-addr=dm-master:8261 query-status aurora-to-tidb-full"
echo ""

