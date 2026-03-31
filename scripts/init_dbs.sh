#!/bin/bash

# Initialize BOTH TiDB Databases for AI State Management
# This script creates:
#   1. ai_memory - Regular database without placement rules
#   2. ai_memory_colocated - Database with placement rules for bot-based colocation

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  TiDB Dual Database Initialization${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""

# Initialize regular database
echo -e "${GREEN}Step 1: Initializing regular database (ai_memory)${NC}"
echo ""
"${SCRIPT_DIR}/init_db.sh"

echo ""
echo -e "${BLUE}───────────────────────────────────────────────────────${NC}"
echo ""

# Initialize colocated database
echo -e "${GREEN}Step 2: Initializing colocated database (ai_memory_colocated)${NC}"
echo ""
"${SCRIPT_DIR}/init_db_colocated.sh"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Both databases initialized successfully!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo ""
echo "Next steps:"
echo "  • Load data into regular DB:    make seed-db"
echo "  • Load data into colocated DB:  make seed-db-colocated"
echo "  • Run placement demo:           make demo-placement"
echo ""

