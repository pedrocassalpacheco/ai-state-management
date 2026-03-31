#!/usr/bin/env python3
"""
Shared configuration for AI State Management scripts.
"""

import os
from pathlib import Path

# Database Configuration
TIDB_HOST = os.getenv("TIDB_HOST", "127.0.0.1")
TIDB_PORT = int(os.getenv("TIDB_PORT", "3306"))
TIDB_USER = os.getenv("TIDB_USER", "root")
TIDB_PASSWORD = os.getenv("TIDB_PASSWORD", "")
TIDB_DATABASE = os.getenv("TIDB_DATABASE", "ai_memory")

# Data Generation Configuration
NUM_USERS = 100
NUM_BOTS = 15
MIN_SESSIONS_PER_USER = 2
MAX_SESSIONS_PER_USER = 8
MIN_MESSAGES_PER_SESSION = 10
MAX_MESSAGES_PER_SESSION = 50
SNAPSHOT_EVERY_N_MESSAGES = 7
TARGET_SNAPSHOTS = 1000

# File Configuration
DATA_DIR = Path(__file__).parent.parent / "data" / "seed"
BATCH_SIZE = 100  # Batch size for database inserts

# Ollama Configuration
EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_DIMENSION = 768
