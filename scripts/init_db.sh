#!/bin/bash

# Initialize TiDB Schema for AI State Management
# This script creates the database schema on the TiDB cluster

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
TIDB_HOST="${TIDB_HOST:-127.0.0.1}"
TIDB_PORT="${TIDB_PORT:-3306}"  # Default to HAProxy load balancer
TIDB_USER="${TIDB_USER:-root}"
TIDB_PASSWORD="${TIDB_PASSWORD:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMA_FILE="${SCRIPT_DIR}/init_schema.sql"

echo -e "${GREEN}TiDB Schema Initialization${NC}"
echo "================================"
echo "Host: ${TIDB_HOST}"
echo "Port: ${TIDB_PORT}"
echo "User: ${TIDB_USER}"
echo ""

# Check if mysql client is available
if ! command -v mysqlsh &> /dev/null; then
    echo -e "${RED}Error: mysqlsh is not installed${NC}"

    exit 1
fi

# Check if schema file exists
if [ ! -f "${SCHEMA_FILE}" ]; then
    echo -e "${RED}Error: Schema file not found: ${SCHEMA_FILE}${NC}"
    exit 1
fi

# Test connection
echo -e "${YELLOW}Testing connection to TiDB...${NC}"
if [ -z "${TIDB_PASSWORD}" ]; then
    mysqlsh -h "${TIDB_HOST}" -P "${TIDB_PORT}" -u "${TIDB_USER}" --no-password -e "SELECT VERSION();" > /dev/null 2>&1
else
    mysqlsh -h "${TIDB_HOST}" -P "${TIDB_PORT}" -u "${TIDB_USER}" -p"${TIDB_PASSWORD}" -e "SELECT VERSION();" > /dev/null 2>&1
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Connection successful${NC}"
else
    echo -e "${RED}✗ Connection failed${NC}"
    echo "Make sure TiDB is running (try: make status)"
    exit 1
fi

# Execute schema file
echo ""
echo -e "${YELLOW}Creating database schema...${NC}"
if [ -z "${TIDB_PASSWORD}" ]; then
    mysqlsh -h "${TIDB_HOST}" -P "${TIDB_PORT}" -u "${TIDB_USER}" --no-password < "${SCHEMA_FILE}"
else
    mysqlsh -h "${TIDB_HOST}" -P "${TIDB_PORT}" -u "${TIDB_USER}" -p"${TIDB_PASSWORD}" < "${SCHEMA_FILE}"
fi

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ Schema created successfully!${NC}"
    echo ""
    echo "Database 'ai_memory' is ready."
    echo ""
    echo "Tables created:"
    if [ -z "${TIDB_PASSWORD}" ]; then
        mysqlsh -h "${TIDB_HOST}" -P "${TIDB_PORT}" -u "${TIDB_USER}" --no-password -e "USE ai_memory; SHOW TABLES;"
    else
        mysqlsh -h "${TIDB_HOST}" -P "${TIDB_PORT}" -u "${TIDB_USER}" -p"${TIDB_PASSWORD}" -e "USE ai_memory; SHOW TABLES;"
    fi
else
    echo -e "${RED}✗ Schema creation failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Done! You can now connect to the database:${NC}"
echo "  mysql -h ${TIDB_HOST} -P ${TIDB_PORT} -u ${TIDB_USER} ai_memory"
