#!/usr/bin/env python3
"""
Load test data from JSONL files into database.

Loads data in correct order to respect foreign key constraints:
1. Users
2. Bots  
3. Sessions
4. Messages
5. Memory Snapshots

Usage:
  python load_test_data.py aurora  # Load into Aurora (ai_state_management)
  python load_test_data.py tidb    # Load into TiDB (ai_state_management - partitioned)
"""

import json
import pymysql
from typing import List, Dict
import sys
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

# Database Configuration
AURORA_HOST = os.getenv("AURORA_HOST")
AURORA_PORT = int(os.getenv("AURORA_PORT", "3306"))
AURORA_USER = os.getenv("AURORA_USER", "admin")
AURORA_PASSWORD = os.getenv("AURORA_PASSWORD", "")
AURORA_DATABASE = os.getenv("AURORA_DATABASE", "ai_state_management")

TIDB_HOST = os.getenv("TIDB_HOST", "127.0.0.1")
TIDB_PORT = int(os.getenv("TIDB_PORT", "3306"))
TIDB_USER = os.getenv("TIDB_USER", "root")
TIDB_PASSWORD = os.getenv("TIDB_PASSWORD", "")
TIDB_DATABASE = os.getenv("TIDB_DATABASE", "ai_state_management")

# File Configuration
DATA_DIR = project_root / "data" / "seed"
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))

def connect_db(db_type='aurora'):
    """Connect to database based on target.
    
    Args:
        db_type: Database type - 'aurora' or 'tidb'
    """
    if db_type == 'tidb':
        # Connect to TiDB (partitioned)
        try:
            connection = pymysql.connect(
                host=TIDB_HOST,
                port=TIDB_PORT,
                user=TIDB_USER,
                password=TIDB_PASSWORD,
                database=TIDB_DATABASE,
                cursorclass=pymysql.cursors.DictCursor
            )
            print(f"✓ Connected to TiDB at {TIDB_HOST}:{TIDB_PORT}")
            print(f"  Database: {TIDB_DATABASE}")
            return connection
        except Exception as e:
            print(f"✗ Failed to connect to TiDB: {e}")
            print("\nMake sure:")
            print("  1. TiDB cluster is running (make up)")
            print("  2. Database schema is initialized (make init-db-colocated)")
            sys.exit(1)
    elif db_type == 'aurora':
        # Connect to Aurora (non-partitioned)
        if not AURORA_HOST:
            print("✗ AURORA_HOST not set in environment variables")
            print("\nPlease configure Aurora credentials in .env file:")
            print("  AURORA_HOST=your-aurora-endpoint.rds.amazonaws.com")
            print("  AURORA_USER=admin")
            print("  AURORA_PASSWORD=your-password")
            sys.exit(1)
        
        try:
            connection = pymysql.connect(
                host=AURORA_HOST,
                port=AURORA_PORT,
                user=AURORA_USER,
                password=AURORA_PASSWORD,
                database=AURORA_DATABASE,
                cursorclass=pymysql.cursors.DictCursor
            )
            print(f"✓ Connected to Aurora RDS MySQL at {AURORA_HOST}")
            print(f"  Database: {AURORA_DATABASE}")
            return connection
        except Exception as e:
            print(f"✗ Failed to connect to Aurora: {e}")
            sys.exit(1)
    else:
        print(f"✗ Invalid database type: {db_type}")
        print("Expected 'aurora' or 'tidb'")
        sys.exit(1)

def load_jsonl(filename: str) -> List[Dict]:
    """Load data from JSONL file."""
    filepath = DATA_DIR / filename
    data = []
    
    if not filepath.exists():
        print(f"✗ File not found: {filepath}")
        return data
    
    with open(filepath, 'r') as f:
        for line in f:
            data.append(json.loads(line.strip()))
    
    return data

def insert_users(connection, users: List[Dict]):
    """Insert users into database."""
    if not users:
        return
    
    print(f"\nInserting {len(users)} users...")
    
    with connection.cursor() as cursor:
        for i in range(0, len(users), BATCH_SIZE):
            batch = users[i:i + BATCH_SIZE]
            
            for user in batch:
                cursor.execute("""
                    INSERT INTO users (user_id, username, email, created_at, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    user['user_id'],
                    user['username'],
                    user['email'],
                    user['created_at'],
                    user['metadata']
                ))
            
            connection.commit()
            print(f"  ✓ Inserted {min(i + BATCH_SIZE, len(users))}/{len(users)} users")
    
    print(f"✓ All users inserted")

def insert_bots(connection, bots: List[Dict]):
    """Insert bots into database."""
    if not bots:
        return
    
    print(f"\nInserting {len(bots)} bots...")
    
    with connection.cursor() as cursor:
        for bot in bots:
            cursor.execute("""
                INSERT INTO bots (bot_id, bot_name, bot_type, system_prompt, config, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    bot_name = VALUES(bot_name),
                    system_prompt = VALUES(system_prompt),
                    config = VALUES(config)
            """, (
                bot['bot_id'],
                bot['bot_name'],
                bot['bot_type'],
                bot['system_prompt'],
                bot['config'],
                bot['is_active']
            ))
        
        connection.commit()
    
    print(f"✓ All bots inserted")

def insert_sessions(connection, sessions: List[Dict]):
    """Insert sessions into database."""
    if not sessions:
        return
    
    print(f"\nInserting {len(sessions)} sessions...")
    
    with connection.cursor() as cursor:
        for i in range(0, len(sessions), BATCH_SIZE):
            batch = sessions[i:i + BATCH_SIZE]
            
            for session in batch:
                cursor.execute("""
                    INSERT INTO sessions 
                    (session_id, user_id, bot_id, started_at, last_active_at, 
                     status, message_count, total_tokens, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session['session_id'],
                    session['user_id'],
                    session['bot_id'],
                    session['started_at'],
                    session['last_active_at'],
                    session['status'],
                    session['message_count'],
                    session['total_tokens'],
                    session['metadata']
                ))
            
            connection.commit()
            print(f"  ✓ Inserted {min(i + BATCH_SIZE, len(sessions))}/{len(sessions)} sessions")
    
    print(f"✓ All sessions inserted")

def check_column_exists(connection, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) as col_count
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = %s 
            AND COLUMN_NAME = %s
        """, (table_name, column_name))
        result = cursor.fetchone()
        return result['col_count'] > 0

def insert_messages(connection, messages: List[Dict]):
    """Insert messages into database.
    
    Messages table only has session_id (no user_id/bot_id columns).
    Both standard and colocated databases have identical schema.
    """
    if not messages:
        return
    
    print(f"\nInserting {len(messages)} messages...")
    
    with connection.cursor() as cursor:
        for i in range(0, len(messages), BATCH_SIZE):
            batch = messages[i:i + BATCH_SIZE]
            
            for message in batch:
                # All databases use session_id only
                cursor.execute("""
                    INSERT INTO messages 
                    (session_id, role, content, created_at, tokens_used, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    message['session_id'],
                    message['role'],
                    message['content'],
                    message['created_at'],
                    message['tokens_used'],
                    message.get('metadata')
                ))
            
            connection.commit()
            
            if (i + BATCH_SIZE) % 1000 == 0 or i + BATCH_SIZE >= len(messages):
                print(f"  ✓ Inserted {min(i + BATCH_SIZE, len(messages))}/{len(messages)} messages")
    
    print(f"✓ All messages inserted")

def insert_memory_snapshots(connection, snapshots: List[Dict]):
    """Insert memory snapshots into database."""
    if not snapshots:
        return
    
    print(f"\nInserting {len(snapshots)} memory snapshots...")
    
    with connection.cursor() as cursor:
        for i in range(0, len(snapshots), BATCH_SIZE):
            batch = snapshots[i:i + BATCH_SIZE]
            
            for snapshot in batch:
                cursor.execute("""
                    INSERT INTO memory_snapshots 
                    (snapshot_id, session_id, user_id, bot_id, summary, key_facts,
                     embedding, created_at, message_count, importance_score, topics, entities)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    snapshot['snapshot_id'],
                    snapshot['session_id'],
                    snapshot['user_id'],
                    snapshot['bot_id'],
                    snapshot['summary'],
                    snapshot['key_facts'],
                    snapshot['embedding'],
                    snapshot['created_at'],
                    snapshot['message_count'],
                    snapshot['importance_score'],
                    snapshot['topics'],
                    snapshot['entities']
                ))
            
            connection.commit()
            print(f"  ✓ Inserted {min(i + BATCH_SIZE, len(snapshots))}/{len(snapshots)} snapshots")
    
    print(f"✓ All memory snapshots inserted")

def get_table_counts(connection):
    """Get record counts from all tables."""
    tables = ['users', 'bots', 'sessions', 'messages', 'memory_snapshots']
    counts = {}
    
    with connection.cursor() as cursor:
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            result = cursor.fetchone()
            counts[table] = result['count']
    
    return counts

def main():
    """Load test data into the database."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Load test data into database',
        usage='%(prog)s [aurora|tidb]'
    )
    parser.add_argument(
        'db_type',
        choices=['aurora', 'tidb'],
        help='Database type: aurora (non-partitioned) or tidb (partitioned)'
    )
    args = parser.parse_args()
    
    # Determine which database to use
    db_label = f"TiDB ({TIDB_DATABASE})" if args.db_type == 'tidb' else f"Aurora RDS MySQL ({AURORA_DATABASE})"
    
    print("=" * 60)
    print(f"Loading Test Data into {db_label}")
    print("=" * 60)
    
    # Check if data files exist
    if not DATA_DIR.exists():
        print(f"✗ Data directory not found: {DATA_DIR}")
        print("\nRun this first: make generate-data")
        sys.exit(1)
    
    # Connect to database
    connection = connect_db(db_type=args.db_type)
    
    try:
        # Get initial counts
        print("\nCurrent database state:")
        initial_counts = get_table_counts(connection)
        for table, count in initial_counts.items():
            print(f"  {table}: {count} records")
        
        # Load data from files
        print("\nLoading data from JSONL files...")
        users = load_jsonl("users.jsonl")
        bots = load_jsonl("bots.jsonl")
        sessions = load_jsonl("sessions.jsonl")
        messages = load_jsonl("messages.jsonl")
        snapshots = load_jsonl("memory_snapshots.jsonl")
        
        print(f"\nLoaded from files:")
        print(f"  Users: {len(users)}")
        print(f"  Bots: {len(bots)}")
        print(f"  Sessions: {len(sessions)}")
        print(f"  Messages: {len(messages)}")
        print(f"  Memory Snapshots: {len(snapshots)}")
        
        # Insert data in correct order (respecting foreign keys)
        insert_users(connection, users)
        insert_bots(connection, bots)
        insert_sessions(connection, sessions)
        insert_messages(connection, messages)
        insert_memory_snapshots(connection, snapshots)
        
        # Get final counts
        print("\n" + "=" * 60)
        print("Final database state:")
        print("=" * 60)
        final_counts = get_table_counts(connection)
        for table, count in final_counts.items():
            added = count - initial_counts[table]
            print(f"  {table}: {count} records (+{added})")
        
        print("\n" + "=" * 60)
        print("✓ Data loading complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        connection.close()
        print("\n✓ Database connection closed")

if __name__ == "__main__":
    main()
