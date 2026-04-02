#!/bin/bash

# Reset Database for AI State Management
# Supports both Aurora RDS MySQL and TiDB
# 
# Usage:
#   ./reset_db.sh aurora  # Reset Aurora RDS MySQL database
#   ./reset_db.sh tidb    # Reset TiDB database

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load environment variables from .env file
if [ -f "${PROJECT_ROOT}/.env" ]; then
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
fi

# Parse command line argument
DB_TYPE="${1:-tidb}"

if [ "$DB_TYPE" != "aurora" ] && [ "$DB_TYPE" != "tidb" ]; then
    echo -e "${RED}Error: Invalid argument '${DB_TYPE}'${NC}"
    echo ""
    echo "Usage: $0 [aurora|tidb]"
    echo "  aurora - Reset Aurora RDS MySQL database"
    echo "  tidb   - Reset TiDB database (default)"
    exit 1
fi

# Configure based on database type
if [ "$DB_TYPE" = "aurora" ]; then
    # Aurora configuration
    DB_HOST="${AURORA_HOST}"
    DB_PORT="${AURORA_PORT:-3306}"
    DB_USER="${AURORA_USER}"
    DB_PASSWORD="${AURORA_PASSWORD}"
    DB_DATABASE="${AURORA_DATABASE}"
    DB_LABEL="Aurora RDS MySQL"
    
    # Validate Aurora configuration
    if [ -z "${AURORA_HOST}" ]; then
        echo -e "${RED}Error: AURORA_HOST not set${NC}"
        echo ""
        echo "Please configure Aurora in .env file"
        exit 1
    fi
else
    # TiDB configuration
    DB_HOST="${TIDB_HOST:-127.0.0.1}"
    DB_PORT="${TIDB_PORT:-3306}"
    DB_USER="${TIDB_USER:-root}"
    DB_PASSWORD="${TIDB_PASSWORD:-}"
    DB_DATABASE="${TIDB_DATABASE}"
    DB_LABEL="TiDB"
fi

# Display warning
echo ""
echo -e "${RED}⚠️  WARNING: This will delete ALL data!${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "  Database: ${DB_DATABASE}"
echo "  Target:   ${DB_LABEL}"
echo "  Host:     ${DB_HOST}:${DB_PORT}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Ask for confirmation
read -p "Are you sure you want to drop the database? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Check if mysqlsh client is available
if ! command -v mysqlsh &> /dev/null; then
    echo -e "${RED}Error: mysqlsh client is not installed${NC}"
    exit 1
fi

# Drop database
echo ""
echo -e "${YELLOW}Dropping database ${DB_DATABASE}...${NC}"

if [ -z "${DB_PASSWORD}" ]; then
    mysqlsh -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" --no-password --sql -e "DROP DATABASE IF EXISTS ${DB_DATABASE};" 2>/dev/null
else
    mysqlsh -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" --sql -e "DROP DATABASE IF EXISTS ${DB_DATABASE};" 2>/dev/null
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database '${DB_DATABASE}' dropped successfully${NC}"
    echo ""
    echo "To recreate the database, run:"
    if [ "$DB_TYPE" = "aurora" ]; then
        echo "  make init-db-aurora"
    else
        echo "  make init-db-tidb"
    fi
    echo ""
else
    echo -e "${RED}✗ Failed to drop database${NC}"
    exit 1
fi
