#!/usr/bin/env -S uv run python
"""
Check table counts between Aurora and TiDB databases.
Simple script to verify data synchronization status.
"""

import pymysql
import os
import sys
from dotenv import load_dotenv

# Colors for terminal output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
NC = '\033[0m'  # No Color


def main():
    # Load environment variables
    load_dotenv()
    
    # Aurora configuration
    aurora_config = {
        'host': os.getenv('AURORA_HOST'),
        'port': int(os.getenv('AURORA_PORT', 3306)),
        'user': os.getenv('AURORA_USER'),
        'password': os.getenv('AURORA_PASSWORD'),
        'database': os.getenv('AURORA_DATABASE', 'ai_state_management'),
    }
    
    # TiDB configuration
    tidb_config = {
        'host': os.getenv('TIDB_HOST', '127.0.0.1'),
        'port': int(os.getenv('TIDB_PORT', 3306)),
        'user': os.getenv('TIDB_USER', 'root'),
        'password': os.getenv('TIDB_PASSWORD', ''),
        'database': os.getenv('TIDB_DATABASE', 'ai_state_management'),
    }
    
    # Tables to check
    tables = ['users', 'bots', 'sessions', 'messages', 'memory_snapshots']
    
    print(f"\n{YELLOW}Database Sync Check{NC}")
    print("=" * 85)
    print(f"Aurora: {aurora_config['host']}")
    print(f"TiDB:   {tidb_config['host']}:{tidb_config['port']}")
    print("=" * 85)
    print()
    
    # Connect to Aurora
    try:
        aurora_conn = pymysql.connect(
            **aurora_config,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10
        )
        print(f"{GREEN}✓{NC} Connected to Aurora")
    except Exception as e:
        print(f"{RED}✗ Aurora connection failed: {e}{NC}")
        sys.exit(1)
    
    # Connect to TiDB
    try:
        tidb_conn = pymysql.connect(
            **tidb_config,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10
        )
        print(f"{GREEN}✓{NC} Connected to TiDB")
    except Exception as e:
        print(f"{RED}✗ TiDB connection failed: {e}{NC}")
        aurora_conn.close()
        sys.exit(1)
    
    print()
    
    # Fetch counts
    aurora_counts = {}
    tidb_counts = {}
    
    with aurora_conn.cursor() as cursor:
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            aurora_counts[table] = cursor.fetchone()['count']
    
    with tidb_conn.cursor() as cursor:
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            tidb_counts[table] = cursor.fetchone()['count']
    
    # Display results
    print("Table Count Comparison")
    print("=" * 85)
    print(f"{'Table':<25} {'Aurora':<20} {'TiDB':<20} {'Status':<20}")
    print("=" * 85)
    
    all_synced = True
    total_aurora = 0
    total_tidb = 0
    
    for table in tables:
        aurora_count = aurora_counts[table]
        tidb_count = tidb_counts[table]
        
        total_aurora += aurora_count
        total_tidb += tidb_count
        
        if aurora_count == tidb_count:
            status = f"{GREEN}✓ Synced{NC}"
        else:
            diff = tidb_count - aurora_count
            status = f"{RED}✗ Diff: {diff:+,}{NC}"
            all_synced = False
        
        print(f"{table:<25} {aurora_count:<20,} {tidb_count:<20,} {status}")
    
    print("=" * 85)
    
    if all_synced:
        total_status = f"{GREEN}✓ Match{NC}"
    else:
        total_status = f"{RED}✗ Mismatch{NC}"
    
    print(f"{'TOTAL':<25} {total_aurora:<20,} {total_tidb:<20,} {total_status}")
    print("=" * 85)
    print()
    
    # Close connections
    aurora_conn.close()
    tidb_conn.close()
    
    # Exit with appropriate code
    if all_synced:
        print(f"{GREEN}✓ All tables are in sync{NC}\n")
        sys.exit(0)
    else:
        print(f"{YELLOW}⚠ Tables are not in sync{NC}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
