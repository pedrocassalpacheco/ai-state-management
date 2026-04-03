#!/usr/bin/env python3
"""Verify Aurora binlog format is set to ROW."""

import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

conn = pymysql.connect(
    host=os.getenv('AURORA_HOST'),
    user=os.getenv('AURORA_USER'),
    password=os.getenv('AURORA_PASSWORD'),
    port=int(os.getenv('AURORA_PORT', 3306))
)

cursor = conn.cursor()
cursor.execute("SHOW VARIABLES LIKE 'binlog_format'")
result = cursor.fetchone()
conn.close()

print(f"Aurora binlog_format: {result[1]}")

