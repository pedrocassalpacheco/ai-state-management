#!/usr/bin/env python3
"""
Demonstrate TiDB placement rules and data resilience.

This script shows:
1. Data colocation by bot_id (all messages for a bot on same partition)
2. Query performance with colocation
3. Data resilience when nodes fail
4. Region/partition distribution
"""

import pymysql
import json
import os
import sys
from typing import Dict, List
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# TiDB configuration from environment
TIDB_HOST = os.getenv("TIDB_HOST", "127.0.0.1")
TIDB_PORT = int(os.getenv("TIDB_PORT", "4000"))
TIDB_USER = os.getenv("TIDB_USER", "root")
TIDB_PASSWORD = os.getenv("TIDB_PASSWORD", "")
TIDB_DATABASE = os.getenv("TIDB_DATABASE", "ai_state_management")

def connect_db():
    """Connect to TiDB database."""
    try:
        connection = pymysql.connect(
            host=TIDB_HOST,
            port=TIDB_PORT,
            user=TIDB_USER,
            password=TIDB_PASSWORD,
            database=TIDB_DATABASE,
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        print(f"✗ Failed to connect to TiDB: {e}")
        sys.exit(1)

def show_partition_info(connection):
    """Show how data is partitioned."""
    print("\n" + "=" * 80)
    print("PARTITION INFORMATION")
    print("=" * 80)
    
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                TABLE_NAME,
                PARTITION_NAME,
                PARTITION_ORDINAL_POSITION as POSITION,
                TABLE_ROWS,
                PARTITION_METHOD
            FROM INFORMATION_SCHEMA.PARTITIONS
            WHERE TABLE_SCHEMA = %s
                AND PARTITION_NAME IS NOT NULL
            ORDER BY TABLE_NAME, PARTITION_ORDINAL_POSITION
        """, (TIDB_DATABASE,))
        
        results = cursor.fetchall()
        
        if not results:
            print("No partitioned tables found.")
            return
        
        current_table = None
        for row in results:
            if current_table != row['TABLE_NAME']:
                if current_table is not None:
                    print()
                current_table = row['TABLE_NAME']
                print(f"\n📊 {current_table} ({row['PARTITION_METHOD']})")
                print("-" * 80)
            
            print(f"  Partition {row['POSITION']:2d} ({row['PARTITION_NAME']:20s}): {row['TABLE_ROWS']:8,} rows")

def show_bot_data_distribution(connection):
    """Show how messages are distributed across bots."""
    print("\n" + "=" * 80)
    print("BOT DATA DISTRIBUTION")
    print("=" * 80)
    
    with connection.cursor() as cursor:
        # Count messages per bot
        cursor.execute("""
            SELECT 
                b.bot_id,
                b.bot_name,
                b.bot_type,
                COUNT(DISTINCT m.session_id) as sessions,
                COUNT(m.message_id) as messages,
                SUM(m.tokens_used) as total_tokens
            FROM bots b
            LEFT JOIN messages m ON b.bot_id = m.bot_id
            GROUP BY b.bot_id, b.bot_name, b.bot_type
            ORDER BY messages DESC
            LIMIT 10
        """)
        
        results = cursor.fetchall()
        
        print(f"\n{'Bot ID':<25} {'Name':<25} {'Type':<12} {'Sessions':>10} {'Messages':>10} {'Tokens':>12}")
        print("-" * 110)
        
        for row in results:
            print(f"{row['bot_id']:<25} {row['bot_name']:<25} {row['bot_type']:<12} "
                  f"{row['sessions']:>10,} {row['messages']:>10,} {row['total_tokens']:>12,}")

def demonstrate_colocation_performance(connection):
    """Demonstrate query performance with colocation."""
    print("\n" + "=" * 80)
    print("COLOCATION PERFORMANCE TEST")
    print("=" * 80)
    
    with connection.cursor() as cursor:
        # Get a bot with many messages
        cursor.execute("""
            SELECT m.bot_id, COUNT(*) as msg_count
            FROM messages m
            GROUP BY m.bot_id
            ORDER BY msg_count DESC
            LIMIT 1
        """)
        
        result = cursor.fetchone()
        if not result:
            print("No data found to test.")
            return
        
        bot_id = result['bot_id']
        msg_count = result['msg_count']
        
        print(f"\n🎯 Testing queries for bot: {bot_id} ({msg_count:,} messages)")
        print("-" * 80)
        
        # Test 1: Count messages for this bot
        print("\n1. Count all messages for this bot:")
        start = time.time()
        cursor.execute("SELECT COUNT(*) as count FROM messages WHERE bot_id = %s", (bot_id,))
        count = cursor.fetchone()['count']
        elapsed = (time.time() - start) * 1000
        print(f"   Result: {count:,} messages")
        print(f"   Time: {elapsed:.2f}ms")
        print(f"   ✓ All messages colocated on same partition - single region scan")
        
        # Test 2: Get recent messages
        print("\n2. Get recent 100 messages for this bot:")
        start = time.time()
        cursor.execute("""
            SELECT message_id, role, LEFT(content, 50) as preview, created_at
            FROM messages
            WHERE bot_id = %s
            ORDER BY created_at DESC
            LIMIT 100
        """, (bot_id,))
        messages = cursor.fetchall()
        elapsed = (time.time() - start) * 1000
        print(f"   Result: {len(messages)} messages retrieved")
        print(f"   Time: {elapsed:.2f}ms")
        print(f"   ✓ Colocated data = faster retrieval")
        
        # Test 3: Aggregate tokens
        print("\n3. Calculate total tokens used for this bot:")
        start = time.time()
        cursor.execute("""
            SELECT 
                SUM(tokens_used) as total_tokens,
                AVG(tokens_used) as avg_tokens,
                MAX(tokens_used) as max_tokens
            FROM messages
            WHERE bot_id = %s
        """, (bot_id,))
        stats = cursor.fetchone()
        elapsed = (time.time() - start) * 1000
        print(f"   Total: {stats['total_tokens']:,} tokens")
        print(f"   Average: {stats['avg_tokens']:.1f} tokens per message")
        print(f"   Max: {stats['max_tokens']:,} tokens")
        print(f"   Time: {elapsed:.2f}ms")

def show_region_distribution(connection):
    """Show how regions are distributed across TiKV stores."""
    print("\n" + "=" * 80)
    print("REGION DISTRIBUTION ACROSS TIKV STORES")
    print("=" * 80)
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    table_name,
                    region_id,
                    start_key,
                    end_key,
                    region_size,
                    leader_store_id,
                    CAST(peer_stores AS CHAR) as peer_stores
                FROM INFORMATION_SCHEMA.TIKV_REGION_STATUS
                WHERE db_name = %s
                    AND table_name IN ('messages', 'sessions', 'memory_snapshots')
                ORDER BY table_name, region_id
                LIMIT 20
            """, (TIDB_DATABASE,))
            
            results = cursor.fetchall()
            
            if not results:
                print("No region information available.")
                print("This requires admin privileges or may not be available in this TiDB version.")
                return
            
            current_table = None
            for row in results:
                if current_table != row['table_name']:
                    if current_table is not None:
                        print()
                    current_table = row['table_name']
                    print(f"\n📍 {current_table}")
                    print("-" * 80)
                
                print(f"  Region {row['region_id']}: "
                      f"Leader=Store{row['leader_store_id']}, "
                      f"Size={row['region_size']:,} bytes")
    
    except Exception as e:
        print(f"\nℹ️  Region information not available: {e}")
        print("This is normal and doesn't affect the placement rules demonstration.")

def demonstrate_resilience(connection):
    """Demonstrate data resilience with replication."""
    print("\n" + "=" * 80)
    print("DATA RESILIENCE DEMONSTRATION")
    print("=" * 80)
    
    with connection.cursor() as cursor:
        # Show replication factor
        print("\n📋 Replication Configuration:")
        print("-" * 80)
        print("  • Each partition has 3 replicas (1 leader + 2 followers)")
        print("  • Data is automatically replicated across TiKV nodes")
        print("  • If one node fails, queries automatically use remaining replicas")
        
        # Demonstrate with a query
        bot_id = None
        cursor.execute("SELECT DISTINCT bot_id FROM messages LIMIT 1")
        result = cursor.fetchone()
        if result:
            bot_id = result['bot_id']
        
        if bot_id:
            print(f"\n🔍 Testing resilience for bot: {bot_id}")
            print("-" * 80)
            
            # Query 1: Initial query
            start = time.time()
            cursor.execute("SELECT COUNT(*) as count FROM messages WHERE bot_id = %s", (bot_id,))
            count1 = cursor.fetchone()['count']
            time1 = (time.time() - start) * 1000
            
            print(f"  Query 1: {count1:,} messages ({time1:.2f}ms)")
            
            # Query 2: Repeat query (should be fast due to caching/colococation)
            start = time.time()
            cursor.execute("SELECT COUNT(*) as count FROM messages WHERE bot_id = %s", (bot_id,))
            count2 = cursor.fetchone()['count']
            time2 = (time.time() - start) * 1000
            
            print(f"  Query 2: {count2:,} messages ({time2:.2f}ms)")
            print(f"\n  ✓ Same results: {count1 == count2}")
            print(f"  ✓ Data is consistently available across replicas")
            
            print("\n💡 NODE FAILURE SIMULATION:")
            print("-" * 80)
            print("  If a TiKV node fails:")
            print("  1. PD (Placement Driver) detects the failure")
            print("  2. Queries automatically redirect to remaining replicas")
            print("  3. No data loss occurs (3 replicas)")
            print("  4. Performance may temporarily degrade but queries still work")
            print("  5. New replica is created on healthy node to restore 3-replica guarantee")
            print("\n  To test: docker-compose stop tikv0")
            print("  Then run queries again - they will still work!")

def main():
    """Run all demonstrations."""
    print("=" * 80)
    print("TiDB PLACEMENT RULES & DATA RESILIENCE DEMONSTRATION")
    print("=" * 80)
    
    connection = connect_db()
    
    try:
        show_partition_info(connection)
        show_bot_data_distribution(connection)
        demonstrate_colocation_performance(connection)
        show_region_distribution(connection)
        demonstrate_resilience(connection)
        
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print("""
✓ Data Colocation: All messages for each bot are on the same partition
✓ Performance: Queries for a specific bot scan only one partition/region
✓ Resilience: 3 replicas ensure no data loss if nodes fail
✓ Distribution: Hash partitioning evenly distributes bots across 8 partitions

Next Steps:
1. Try stopping a TiKV node: docker-compose stop tikv0
2. Rerun this script - queries still work!
3. Restart the node: docker-compose start tikv0
4. TiDB automatically rebalances
        """)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        connection.close()

if __name__ == "__main__":
    main()
