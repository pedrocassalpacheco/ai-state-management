#!/bin/bash

# Initialize Database Schema for AI State Management
# Supports both Aurora RDS MySQL and TiDB
# 
# Usage:
#   ./init_db_tidb.sh aurora  # Initialize Aurora RDS MySQL
#   ./init_db_tidb.sh tidb    # Initialize TiDB with placement rules

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
    echo "  aurora - Initialize Aurora RDS MySQL"
    echo "  tidb   - Initialize TiDB (default)"
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
    # Handle both relative paths from project root and filenames
    if [ -n "${AURORA_SCHEMA}" ] && [ -f "${PROJECT_ROOT}/${AURORA_SCHEMA}" ]; then
        SCHEMA_FILE="${PROJECT_ROOT}/${AURORA_SCHEMA}"
    else
        SCHEMA_FILE="${SCRIPT_DIR}/init_schema_aurora.sql"
    fi
    DB_LABEL="Aurora RDS MySQL"
    DB_TYPE_LABEL="aurora"
    
    # Validate Aurora configuration
    if [ -z "${AURORA_HOST}" ]; then
        echo -e "${RED}Error: AURORA_HOST not set${NC}"
        echo ""
        echo "Please configure Aurora in .env file:"
        echo "  AURORA_HOST=your-aurora-endpoint.rds.amazonaws.com"
        echo "  AURORA_USER=admin"
        echo "  AURORA_PASSWORD=your-password"
        echo "  AURORA_DATABASE=your_database_name"
        exit 1
    fi
else
    # TiDB configuration
    DB_HOST="${TIDB_HOST:-127.0.0.1}"
    DB_PORT="${TIDB_PORT:-3306}"
    DB_USER="${TIDB_USER:-root}"
    DB_PASSWORD="${TIDB_PASSWORD:-}"
    DB_DATABASE="${TIDB_DATABASE}"
    # Handle both relative paths from project root and filenames
    if [ -n "${TIDB_SCHEMA}" ] && [ -f "${PROJECT_ROOT}/${TIDB_SCHEMA}" ]; then
        SCHEMA_FILE="${PROJECT_ROOT}/${TIDB_SCHEMA}"
    else
        SCHEMA_FILE="${SCRIPT_DIR}/init_schema_tidb.sql"
    fi
    DB_LABEL="TiDB (with Placement Rules)"
    DB_TYPE_LABEL="tidb"
fi

# Display configuration
echo -e "${GREEN}Database Initialization: ${DB_LABEL}${NC}"
echo "=========================================="
echo "Host: ${DB_HOST}"
echo "Port: ${DB_PORT}"
echo "User: ${DB_USER}"
echo "Database: ${DB_DATABASE}"
echo "Schema: ${SCHEMA_FILE}"
echo ""

# Check if mysqlsh client is available
if ! command -v mysqlsh &> /dev/null; then
    echo -e "${RED}Error: mysqlsh client is not installed${NC}"
    echo "Install with: brew install mysql-shell (macOS) or apt-get install mysql-shell (Linux)"
    exit 1
fi

# Check if schema file exists
if [ ! -f "${SCHEMA_FILE}" ]; then
    echo -e "${RED}Error: Schema file not found: ${SCHEMA_FILE}${NC}"
    exit 1
fi

# Test connection
echo -e "${YELLOW}Testing connection to ${DB_LABEL}...${NC}"
if [ -z "${DB_PASSWORD}" ]; then
    mysqlsh -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" --no-password --sql -e "SELECT VERSION();" > /dev/null 2>&1
else
    mysqlsh -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" --sql -e "SELECT VERSION();" > /dev/null 2>&1
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Connection successful${NC}"
else
    echo -e "${RED}✗ Connection failed${NC}"
    if [ "$DB_TYPE" = "aurora" ]; then
        echo "Make sure:"
        echo "  1. Aurora RDS is accessible from this machine"
        echo "  2. Security group allows your IP address"
        echo "  3. Credentials in .env file are correct"
    else
        echo "Make sure TiDB is running (try: make status)"
    fi
    exit 1
fi

# Create database
echo ""
echo -e "${YELLOW}Creating database ${DB_DATABASE}...${NC}"
if [ -z "${DB_PASSWORD}" ]; then
    mysqlsh -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" --no-password --sql -e "CREATE DATABASE IF NOT EXISTS ${DB_DATABASE};"
else
    mysqlsh -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" --sql -e "CREATE DATABASE IF NOT EXISTS ${DB_DATABASE};"
fi

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Database creation failed${NC}"
    exit 1
fi

# Execute schema file
echo ""
echo -e "${YELLOW}Creating database schema...${NC}"
if [ -z "${DB_PASSWORD}" ]; then
    (echo "USE ${DB_DATABASE};"; cat "${SCHEMA_FILE}") | mysqlsh -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" --no-password --sql
else
    (echo "USE ${DB_DATABASE};"; cat "${SCHEMA_FILE}") | mysqlsh -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" --sql
fi

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ Schema created successfully!${NC}"
    echo ""
    echo "Database '${DB_DATABASE}' is ready on ${DB_LABEL}."
    echo ""
    echo "Tables created:"
    if [ -z "${DB_PASSWORD}" ]; then
        mysqlsh -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" --no-password --sql -e "USE ${DB_DATABASE}; SHOW TABLES;"
    else
        mysqlsh -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" --sql -e "USE ${DB_DATABASE}; SHOW TABLES;"
    fi
    
    # Show partition info for TiDB
    if [ "$DB_TYPE" = "tidb" ]; then
        echo ""
        echo "Partitions created:"
        if [ -z "${DB_PASSWORD}" ]; then
            mysqlsh -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" --no-password --sql -e "USE ${DB_DATABASE}; SELECT DISTINCT table_name, COUNT(*) as partitions FROM information_schema.partitions WHERE table_schema='${DB_DATABASE}' GROUP BY table_name;" 2>/dev/null || echo "  ✓ Tables with bot-based partitioning"
        else
            mysqlsh -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" --sql -e "USE ${DB_DATABASE}; SELECT DISTINCT table_name, COUNT(*) as partitions FROM information_schema.partitions WHERE table_schema='${DB_DATABASE}' GROUP BY table_name;" 2>/dev/null || echo "  ✓ Tables with bot-based partitioning"
        fi
    fi
else
    echo -e "${RED}✗ Schema creation failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Done! You can now connect to the database:${NC}"
echo "  mysqlsh -h ${DB_HOST} -P ${DB_PORT} -u ${DB_USER} --sql ${DB_DATABASE}"
echo ""
