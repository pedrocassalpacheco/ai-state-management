#!/usr/bin/env python3
"""Check and compare schemas between ai_memory and ai_memory_colocated databases."""

import pymysql
from config import TIDB_HOST, TIDB_PORT, TIDB_USER, TIDB_PASSWORD

def get_table_schema(db_name, table_name):
    """Get column definitions for a table."""
    conn = pymysql.connect(
        host=TIDB_HOST,
        port=TIDB_PORT,
        user=TIDB_USER,
        password=TIDB_PASSWORD,
        database=db_name
    )
    
    with conn.cursor() as cursor:
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()
    
    conn.close()
    return columns

def main():
    print("=" * 80)
    print("SCHEMA COMPARISON: ai_memory vs ai_memory_colocated")
    print("=" * 80)
    
    # Check messages table
    print("\n### MESSAGES TABLE ###\n")
    
    print("Standard DB (ai_memory):")
    try:
        standard_columns = get_table_schema('ai_memory', 'messages')
        for col in standard_columns:
            print(f"  {col[0]:20s} {col[1]:30s} {col[2]:5s} {col[3]:5s}")
    except Exception as e:
        print(f"  Error: {e}")
    
    print("\nColocated DB (ai_memory_colocated):")
    try:
        colocated_columns = get_table_schema('ai_memory_colocated', 'messages')
        for col in colocated_columns:
            print(f"  {col[0]:20s} {col[1]:30s} {col[2]:5s} {col[3]:5s}")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Check sessions table
    print("\n### SESSIONS TABLE ###\n")
    
    print("Standard DB (ai_memory):")
    try:
        standard_columns = get_table_schema('ai_memory', 'sessions')
        for col in standard_columns:
            print(f"  {col[0]:20s} {col[1]:30s} {col[2]:5s} {col[3]:5s}")
    except Exception as e:
        print(f"  Error: {e}")
    
    print("\nColocated DB (ai_memory_colocated):")
    try:
        colocated_columns = get_table_schema('ai_memory_colocated', 'sessions')
        for col in colocated_columns:
            print(f"  {col[0]:20s} {col[1]:30s} {col[2]:5s} {col[3]:5s}")
    except Exception as e:
        print(f"  Error: {e}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
