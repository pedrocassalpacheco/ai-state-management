-- AI State Management Database Schema with Placement Rules
-- TiDB with data colocation by bot_id for improved locality and resilience

CREATE DATABASE IF NOT EXISTS ai_state_management;
USE ai_state_management;

-- ============================================================================
-- PLACEMENT POLICIES
-- ============================================================================
-- These policies control where data is physically stored in the TiKV cluster
-- Each bot's data will be colocated to minimize cross-node queries

-- Policy for bot type 'assistant' - use all nodes but keep replicas together
CREATE PLACEMENT POLICY IF NOT EXISTS policy_assistant 
    FOLLOWERS=2;

-- Policy for bot type 'support' 
CREATE PLACEMENT POLICY IF NOT EXISTS policy_support 
    FOLLOWERS=2;

-- Policy for bot type 'technical'
CREATE PLACEMENT POLICY IF NOT EXISTS policy_technical 
    FOLLOWERS=2;

-- Default policy for other bot types
CREATE PLACEMENT POLICY IF NOT EXISTS policy_default 
    FOLLOWERS=2;

-- ============================================================================
-- TABLES
-- ============================================================================

-- Users table (no partitioning needed)
CREATE TABLE IF NOT EXISTS users (
    user_id CHAR(36) PRIMARY KEY,
    username VARCHAR(255) UNIQUE,
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    metadata JSON,
    INDEX idx_username (username),
    INDEX idx_last_active (last_active_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Bots table (no partitioning needed)
CREATE TABLE IF NOT EXISTS bots (
    bot_id VARCHAR(100) PRIMARY KEY,
    bot_name VARCHAR(255) NOT NULL,
    bot_type VARCHAR(50),
    system_prompt TEXT,
    config JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_type (bot_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- PARTITIONED TABLES WITH PLACEMENT RULES
-- ============================================================================

-- Sessions table - partitioned by session_id for session-based colocation
-- Note: Foreign keys not supported on partitioned tables in TiDB
CREATE TABLE IF NOT EXISTS sessions (
    session_id CHAR(36) PRIMARY KEY,
    user_id CHAR(36) NOT NULL,
    bot_id VARCHAR(100) NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL,
    status VARCHAR(50) DEFAULT 'active',
    message_count INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    metadata JSON,
    KEY idx_user_bot (user_id, bot_id),
    KEY idx_user_active (user_id, last_active_at),
    KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
PARTITION BY KEY(session_id) PARTITIONS 8;

-- Messages table - partitioned by session_id to colocate all messages for a session
-- This ensures queries for a specific session hit only one partition
CREATE TABLE IF NOT EXISTS messages (
    message_id BIGINT AUTO_INCREMENT,
    session_id CHAR(36) NOT NULL,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),
    tokens_used INT DEFAULT 0,
    model VARCHAR(100),
    finish_reason VARCHAR(50),
    metadata JSON,
    PRIMARY KEY (session_id, message_id),
    KEY idx_session_created (session_id, created_at),
    KEY idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
PARTITION BY KEY(session_id) PARTITIONS 8;

-- Memory snapshots - partitioned by session_id for colocation with messages
CREATE TABLE IF NOT EXISTS memory_snapshots (
    snapshot_id CHAR(36),
    session_id CHAR(36) NOT NULL,
    user_id CHAR(36) NOT NULL,
    bot_id VARCHAR(100) NOT NULL,
    
    -- Memory content
    summary TEXT NOT NULL,
    key_facts JSON,
    
    -- Vector embedding
    embedding JSON COMMENT 'Vector as JSON array',
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_start_id BIGINT,
    message_end_id BIGINT,
    message_count INT DEFAULT 0,
    importance_score FLOAT DEFAULT 0.5,
    
    -- Tags and entities
    topics JSON,
    entities JSON,
    
    PRIMARY KEY (session_id, snapshot_id),
    KEY idx_user_created (user_id, created_at DESC),
    KEY idx_session (session_id),
    KEY idx_importance (importance_score DESC),
    KEY idx_user_bot (user_id, bot_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
PARTITION BY KEY(session_id) PARTITIONS 8;

-- User preferences (no partitioning needed - small table)
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id CHAR(36) PRIMARY KEY,
    language VARCHAR(10) DEFAULT 'en',
    timezone VARCHAR(50) DEFAULT 'UTC',
    preferences JSON,
    consent JSON,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Usage stats - partitioned by (user_id, bot_id) for colocation
CREATE TABLE IF NOT EXISTS usage_stats (
    stat_id BIGINT AUTO_INCREMENT,
    user_id CHAR(36),
    bot_id VARCHAR(100),
    date DATE NOT NULL,
    session_count INT DEFAULT 0,
    message_count INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    avg_session_duration_seconds INT DEFAULT 0,
    metadata JSON,
    PRIMARY KEY (user_id, bot_id, stat_id),
    UNIQUE KEY idx_user_bot_date (user_id, bot_id, date),
    KEY idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
PARTITION BY KEY(user_id, bot_id) PARTITIONS 8;

-- Insert default bot
INSERT INTO bots (bot_id, bot_name, bot_type, system_prompt, config) VALUES
    ('default-assistant', 'Default Assistant', 'assistant', 
     'You are a helpful AI assistant with access to past conversation history.',
     '{"model": "gpt-4", "temperature": 0.7, "max_tokens": 2000}')
ON DUPLICATE KEY UPDATE bot_name=bot_name;

-- ============================================================================
-- VIEWS FOR PLACEMENT VERIFICATION
-- ============================================================================

-- View to see partition distribution
CREATE OR REPLACE VIEW partition_info AS
SELECT 
    TABLE_NAME,
    PARTITION_NAME,
    PARTITION_ORDINAL_POSITION,
    PARTITION_METHOD,
    PARTITION_DESCRIPTION,
    TABLE_ROWS
FROM INFORMATION_SCHEMA.PARTITIONS
WHERE TABLE_SCHEMA = 'ai_memory_colocated'
    AND PARTITION_NAME IS NOT NULL
ORDER BY TABLE_NAME, PARTITION_ORDINAL_POSITION;

-- View to see region distribution (simplified version)
CREATE OR REPLACE VIEW region_distribution AS
SELECT 
    table_name,
    COUNT(DISTINCT region_id) as region_count,
    COUNT(*) as total_regions
FROM INFORMATION_SCHEMA.TIKV_REGION_STATUS
WHERE db_name = 'ai_memory_colocated'
GROUP BY table_name;

-- Show setup
SELECT 'Schema with placement rules created successfully!' as status;
SHOW TABLES;
SELECT * FROM partition_info;
