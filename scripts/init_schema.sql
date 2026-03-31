-- AI State Management Database Schema
-- TiDB with Vector Search capabilities

-- Create main database
CREATE DATABASE IF NOT EXISTS ai_memory;

USE ai_memory;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id CHAR(36) PRIMARY KEY,  -- UUID
    username VARCHAR(255) UNIQUE,
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    metadata JSON,
    INDEX idx_username (username),
    INDEX idx_last_active (last_active_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Chatbot/Agent configurations
CREATE TABLE IF NOT EXISTS bots (
    bot_id VARCHAR(100) PRIMARY KEY,
    bot_name VARCHAR(255) NOT NULL,
    bot_type VARCHAR(50),  -- assistant, support, sales, etc.
    system_prompt TEXT,
    config JSON,  -- model settings, temperature, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_type (bot_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Conversation sessions
CREATE TABLE IF NOT EXISTS sessions (
    session_id CHAR(36) PRIMARY KEY,  -- UUID
    user_id CHAR(36) NOT NULL,
    bot_id VARCHAR(100) NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL,
    status VARCHAR(50) DEFAULT 'active',  -- active, archived, deleted
    message_count INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    metadata JSON,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE,
    INDEX idx_user_active (user_id, last_active_at),
    INDEX idx_bot (bot_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Individual messages
-- No partitioning - messages can be scattered across storage
CREATE TABLE IF NOT EXISTS messages (
    message_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id CHAR(36) NOT NULL,
    role VARCHAR(50) NOT NULL,  -- user, assistant, system, tool
    content TEXT NOT NULL,
    created_at TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),  -- Microsecond precision
    tokens_used INT DEFAULT 0,
    model VARCHAR(100),
    finish_reason VARCHAR(50),  -- stop, length, tool_calls, etc.
    metadata JSON,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    INDEX idx_session_created (session_id, created_at),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Memory snapshots with vector embeddings
CREATE TABLE IF NOT EXISTS memory_snapshots (
    snapshot_id CHAR(36) PRIMARY KEY,  -- UUID
    session_id CHAR(36) NOT NULL,
    user_id CHAR(36) NOT NULL,
    bot_id VARCHAR(100) NOT NULL,
    
    -- Memory content
    summary TEXT NOT NULL,
    key_facts JSON,  -- Structured extracted information
    
    -- Vector embedding for semantic search
    -- Note: Vector support requires TiDB 7.5+
    -- embedding VECTOR(1536) COMMENT 'OpenAI ada-002 or similar',
    embedding JSON COMMENT 'Vector as JSON array until VECTOR type is fully supported',
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_start_id BIGINT,  -- First message in this snapshot
    message_end_id BIGINT,    -- Last message in this snapshot
    message_count INT DEFAULT 0,
    importance_score FLOAT DEFAULT 0.5,  -- 0.0 to 1.0
    
    -- Tags and entities for filtering
    topics JSON,  -- Array of topic strings
    entities JSON,  -- Extracted entities {people: [], places: [], etc.}
    
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE,
    
    INDEX idx_user_created (user_id, created_at DESC),
    INDEX idx_session (session_id),
    INDEX idx_importance (importance_score DESC),
    INDEX idx_user_bot (user_id, bot_id)
    -- Vector index will be added when VECTOR type is available:
    -- VECTOR INDEX idx_embedding (embedding)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- User preferences and settings
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id CHAR(36) PRIMARY KEY,
    language VARCHAR(10) DEFAULT 'en',
    timezone VARCHAR(50) DEFAULT 'UTC',
    preferences JSON,  -- Theme, notification settings, etc.
    consent JSON,  -- Privacy and data usage consents
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Analytics/aggregated stats (optional)
CREATE TABLE IF NOT EXISTS usage_stats (
    stat_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id CHAR(36),
    bot_id VARCHAR(100),
    date DATE NOT NULL,
    session_count INT DEFAULT 0,
    message_count INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    avg_session_duration_seconds INT DEFAULT 0,
    metadata JSON,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (bot_id) REFERENCES bots(bot_id) ON DELETE CASCADE,
    UNIQUE KEY idx_user_bot_date (user_id, bot_id, date),
    INDEX idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert default bot
INSERT INTO bots (bot_id, bot_name, bot_type, system_prompt, config) VALUES
    ('default-assistant', 'Default Assistant', 'assistant', 
     'You are a helpful AI assistant with access to past conversation history.',
     '{"model": "gpt-4", "temperature": 0.7, "max_tokens": 2000}')
ON DUPLICATE KEY UPDATE bot_name=bot_name;

-- Show created tables
SHOW TABLES;

SELECT 'Database schema created successfully!' as status;
