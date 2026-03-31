# Database Schema Documentation

## Overview

The AI State Management system uses a relational database schema designed to store conversational AI interactions, with support for multiple users, multiple bots, and vector-based semantic search.

**Two Database Variants:**
- **`ai_memory`** - Standard schema without partitioning
- **`ai_memory_colocated`** - Partitioned schema for improved query performance (partitioned by user_id + bot_id)

---

## Entity-Relationship Diagram

### Interactive ER Diagram

A detailed Mermaid ER diagram is available in [schema-erd.mmd](./schema-erd.mmd).

**How to view:**

1. **VS Code** (Recommended):
   - Install the "Markdown Preview Mermaid Support" extension
   - Open `schema-erd.mmd` and press `Cmd+Shift+V` (Mac) or `Ctrl+Shift+V` (Windows/Linux)

2. **GitHub**:
   - View the file directly on GitHub - it renders automatically
   - [View online](https://github.com/YOUR_REPO/blob/main/docs/schema-erd.mmd)

3. **Mermaid Live Editor**:
   - Open [mermaid.live](https://mermaid.live)
   - Paste the contents of `schema-erd.mmd`
   - Export as PNG/SVG/PDF

4. **Command Line** (requires mermaid-cli):
   ```bash
   # Install mermaid-cli
   npm install -g @mermaid-js/mermaid-cli
   
   # Generate PNG image
   mmdc -i docs/schema-erd.mmd -o docs/schema-erd.png
   
   # Generate SVG (scalable)
   mmdc -i docs/schema-erd.mmd -o docs/schema-erd.svg
   ```

### Simplified Relationship Overview

```
┌──────────────┐
│    users     │
└──────┬───────┘
       │
       │ 1:N
       ▼
┌──────────────┐         ┌──────────────┐
│   sessions   │◄────────│     bots     │
└──────┬───────┘   N:1   └──────────────┘
       │
       │ 1:N
       ├──────────────────┬──────────────────┐
       │                  │                  │
       ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│   messages   │   │memory_       │   │   usage_stats    │
│              │   │ snapshots    │   │                  │
└──────────────┘   └──────────────┘   └──────────────────┘
```

---

## Core Concept: Why Multiple Tables?

The schema uses separate tables for **sessions**, **messages**, and **memory_snapshots** because they serve different purposes:

| Table | Purpose | Granularity | Use Case |
|-------|---------|-------------|----------|
| **sessions** | Conversation metadata | Per conversation | Track when conversations started, ended, status |
| **messages** | Individual exchanges | Per message | Store exact user/bot messages, content, timing |
| **memory_snapshots** | Summarized state | Periodic checkpoints | Semantic search, conversation summaries, AI context |

**Example:**
- A single **session** (1 conversation) contains multiple **messages** (10-100 exchanges)
- Every N messages, a **memory_snapshot** is created (compressed summary + embedding)
- This allows fast semantic search without scanning every individual message

---

## Data Dictionary

### 1. users

User accounts that interact with the AI chatbots.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `user_id` | CHAR(36) | PRIMARY KEY | UUID identifier for the user |
| `username` | VARCHAR(255) | UNIQUE | User's display name |
| `email` | VARCHAR(255) | | User's email address |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Account creation time |
| `last_active_at` | TIMESTAMP | AUTO UPDATE | Last interaction timestamp |
| `metadata` | JSON | | Additional user data (preferences, profile) |

**Indexes:**
- `idx_username` on `username`
- `idx_last_active` on `last_active_at`

**Purpose:** Central user registry. Acts as parent for all user activities.

---

### 2. bots

AI chatbot configurations and personalities.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `bot_id` | VARCHAR(100) | PRIMARY KEY | Unique bot identifier (e.g., 'assistant-bot-1') |
| `bot_name` | VARCHAR(255) | NOT NULL | Human-readable bot name |
| `bot_type` | VARCHAR(50) | | Bot category (assistant, support, technical, sales) |
| `system_prompt` | TEXT | | System prompt defining bot behavior |
| `config` | JSON | | Model settings (model, temperature, max_tokens) |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Bot creation time |
| `updated_at` | TIMESTAMP | AUTO UPDATE | Last configuration update |
| `is_active` | BOOLEAN | DEFAULT TRUE | Whether bot is currently active |

**Indexes:**
- `idx_type` on `bot_type`

**Purpose:** Stores bot configurations. Each bot can have conversations with many users.

---

### 3. sessions

Conversation sessions between a user and a bot.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `session_id` | CHAR(36) | PRIMARY KEY | UUID for the conversation session |
| `user_id` | CHAR(36) | FK → users | User participating in the session |
| `bot_id` | VARCHAR(100) | FK → bots | Bot participating in the session |
| `started_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Session start time |
| `last_active_at` | TIMESTAMP | AUTO UPDATE | Last message in session |
| `ended_at` | TIMESTAMP | NULL | Session end time (NULL if active) |
| `status` | VARCHAR(50) | DEFAULT 'active' | Session status (active, archived, deleted) |
| `message_count` | INT | DEFAULT 0 | Total messages in this session |
| `total_tokens` | INT | DEFAULT 0 | Total tokens used in this session |
| `metadata` | JSON | | Additional session data |

**Indexes:**
- `idx_user_active` on `(user_id, last_active_at)`
- `idx_bot` on `bot_id`
- `idx_status` on `status`

**Foreign Keys:**
- `user_id` → `users(user_id)` ON DELETE CASCADE
- `bot_id` → `bots(bot_id)` ON DELETE CASCADE

**Purpose:** Tracks conversation boundaries and metadata. One session = one continuous conversation.

**Partitioning (colocated db):**
- Partitioned by `(user_id, bot_id)` using KEY partitioning (8 partitions)
- PRIMARY KEY: `(user_id, bot_id, session_id)`

---

### 4. messages

Individual message exchanges within a session.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `message_id` | BIGINT | PRIMARY KEY AUTO_INCREMENT | Unique message identifier |
| `session_id` | CHAR(36) | FK → sessions | Session this message belongs to |
| `user_id` | CHAR(36) | FK → users | User (denormalized for partitioning) |
| `bot_id` | VARCHAR(100) | FK → bots | Bot (denormalized for partitioning) |
| `role` | VARCHAR(50) | NOT NULL | Message role (user, assistant, system, tool) |
| `content` | TEXT | NOT NULL | Message content/text |
| `created_at` | TIMESTAMP(6) | DEFAULT NOW | Message timestamp (microsecond precision) |
| `tokens_used` | INT | DEFAULT 0 | Token count for this message |
| `model` | VARCHAR(100) | | Model used (for assistant messages) |
| `finish_reason` | VARCHAR(50) | | Completion reason (stop, length, tool_calls) |
| `metadata` | JSON | | Additional message data |

**Indexes:**
- `idx_session_created` on `(session_id, created_at)`
- `idx_user_bot` on `(user_id, bot_id)`
- `idx_bot` on `bot_id`
- `idx_role` on `role`

**Foreign Keys:**
- `session_id` → `sessions(session_id)` ON DELETE CASCADE
- `user_id` → `users(user_id)` ON DELETE CASCADE
- `bot_id` → `bots(bot_id)` ON DELETE CASCADE

**Purpose:** Stores granular message-by-message conversation data. Allows replaying full conversation history.

**Why Denormalized?**
- `user_id` and `bot_id` are denormalized (can be derived from `session_id`)
- **Reason:** Enables partitioning by `(user_id, bot_id)` for data colocation in distributed database
- **Benefit:** All messages from user X to bot Y are in the same partition = faster queries

**Partitioning (colocated db):**
- Partitioned by `(user_id, bot_id)` using KEY partitioning (8 partitions)
- PRIMARY KEY: `(user_id, bot_id, message_id)`

---

### 5. memory_snapshots

Periodic summarized conversation state with vector embeddings for semantic search.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `snapshot_id` | CHAR(36) | PRIMARY KEY | UUID for the memory snapshot |
| `session_id` | CHAR(36) | FK → sessions | Session being summarized |
| `user_id` | CHAR(36) | FK → users | User (denormalized) |
| `bot_id` | VARCHAR(100) | FK → bots | Bot (denormalized) |
| `summary` | TEXT | NOT NULL | Human-readable conversation summary |
| `key_facts` | JSON | | Extracted structured information |
| `embedding` | JSON | | Vector embedding (768-dim, as JSON array) |
| `created_at` | TIMESTAMP | DEFAULT NOW | Snapshot creation time |
| `message_start_id` | BIGINT | | First message ID in this snapshot |
| `message_end_id` | BIGINT | | Last message ID in this snapshot |
| `message_count` | INT | DEFAULT 0 | Number of messages summarized |
| `importance_score` | FLOAT | DEFAULT 0.5 | Snapshot importance (0.0-1.0) |
| `topics` | JSON | | Array of topic strings |
| `entities` | JSON | | Extracted entities (people, places, etc.) |

**Indexes:**
- `idx_user_created` on `(user_id, created_at DESC)`
- `idx_session` on `session_id`
- `idx_importance` on `importance_score DESC`
- `idx_user_bot` on `(user_id, bot_id)`

**Foreign Keys:**
- `session_id` → `sessions(session_id)` ON DELETE CASCADE
- `user_id` → `users(user_id)` ON DELETE CASCADE
- `bot_id` → `bots(bot_id)` ON DELETE CASCADE

**Purpose:** 
- **Semantic Search:** Vector embeddings enable finding similar conversations
- **Context Management:** Summarize long conversations for AI context windows
- **Memory Retrieval:** Quickly retrieve relevant past conversations
- **Performance:** Avoid scanning thousands of individual messages

**Why Separate from Messages?**
- Messages = raw data (every exchange)
- Snapshots = processed data (summarized + embedded)
- Snapshots are created every N messages (e.g., every 20 messages)
- Enables fast semantic search without processing every message

**Partitioning (colocated db):**
- Partitioned by `(user_id, bot_id)` using KEY partitioning (8 partitions)
- PRIMARY KEY: `(user_id, bot_id, snapshot_id)`

---

### 6. user_preferences

User-specific settings and preferences.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `user_id` | CHAR(36) | PRIMARY KEY, FK → users | User identifier |
| `language` | VARCHAR(10) | DEFAULT 'en' | Preferred language code |
| `timezone` | VARCHAR(50) | DEFAULT 'UTC' | User's timezone |
| `preferences` | JSON | | UI preferences (theme, notifications) |
| `consent` | JSON | | Privacy and data usage consents |
| `updated_at` | TIMESTAMP | AUTO UPDATE | Last update time |

**Foreign Keys:**
- `user_id` → `users(user_id)` ON DELETE CASCADE

**Purpose:** Store user-specific settings separate from core user table.

---

### 7. usage_stats

Aggregated usage statistics for analytics.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `stat_id` | BIGINT | PRIMARY KEY AUTO_INCREMENT | Unique stat record ID |
| `user_id` | CHAR(36) | FK → users | User (nullable for bot-level stats) |
| `bot_id` | VARCHAR(100) | FK → bots | Bot (nullable for user-level stats) |
| `date` | DATE | NOT NULL | Date for these statistics |
| `session_count` | INT | DEFAULT 0 | Number of sessions on this date |
| `message_count` | INT | DEFAULT 0 | Number of messages on this date |
| `total_tokens` | INT | DEFAULT 0 | Total tokens used on this date |
| `avg_session_duration_seconds` | INT | DEFAULT 0 | Average session duration |
| `metadata` | JSON | | Additional stats |

**Indexes:**
- `idx_user_bot_date` on `(user_id, bot_id, date)` UNIQUE
- `idx_date` on `date`

**Foreign Keys:**
- `user_id` → `users(user_id)` ON DELETE CASCADE
- `bot_id` → `bots(bot_id)` ON DELETE CASCADE

**Purpose:** Pre-aggregated daily statistics for dashboards and reporting.

**Partitioning (colocated db):**
- Partitioned by `(user_id, bot_id)` using KEY partitioning (8 partitions)
- PRIMARY KEY: `(user_id, bot_id, stat_id)`

---

## Common Query Patterns

### 1. Get All Messages for a User-Bot Conversation
```sql
SELECT * FROM messages 
WHERE user_id = '123e4567-e89b-12d3-a456-426614174000'
  AND bot_id = 'assistant-bot-1'
ORDER BY created_at DESC;
```

**Performance in Colocated DB:** Hits only 1 partition (out of 8)

---

### 2. Find Similar Conversations (Semantic Search)
```sql
-- Conceptual query (vector search not yet fully supported in TiDB)
SELECT snapshot_id, summary, user_id, bot_id
FROM memory_snapshots
WHERE vector_distance(embedding, :query_embedding) < 0.5
ORDER BY importance_score DESC
LIMIT 10;
```

---

### 3. Get Recent Sessions for a User
```sql
SELECT s.*, b.bot_name 
FROM sessions s
JOIN bots b ON s.bot_id = b.bot_id
WHERE s.user_id = '123e4567-e89b-12d3-a456-426614174000'
ORDER BY s.last_active_at DESC
LIMIT 10;
```

---

### 4. Get Daily Stats for a Bot
```sql
SELECT date, 
       SUM(session_count) as total_sessions,
       SUM(message_count) as total_messages,
       SUM(total_tokens) as total_tokens
FROM usage_stats
WHERE bot_id = 'assistant-bot-1'
  AND date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY date
ORDER BY date DESC;
```

---

## Data Flow Example

1. **User starts conversation:**
   - Insert into `sessions` table
   
2. **User sends message:**
   - Insert into `messages` table (role='user')
   - Update `sessions.last_active_at`
   - Increment `sessions.message_count`

3. **Bot responds:**
   - Insert into `messages` table (role='assistant')
   - Update `sessions.total_tokens`

4. **Every 20 messages:**
   - Generate summary of recent messages
   - Generate vector embedding
   - Insert into `memory_snapshots` table

5. **End of day:**
   - Aggregate stats to `usage_stats` table

---

## Schema Design Decisions

### Q: Why denormalize user_id and bot_id in messages?
**A:** Enables efficient partitioning by `(user_id, bot_id)` for data colocation in distributed storage. This makes queries for "all messages from user X to bot Y" much faster (single partition scan vs. full table scan).

### Q: Why separate sessions and messages tables?
**A:** Different granularities and access patterns:
- **Sessions** = metadata, small rows, frequent updates (status, counters)
- **Messages** = content, large rows, write-once
- Allows efficient queries for "user's active sessions" without loading message content

### Q: Why have memory_snapshots when we already have messages?
**A:** Different purposes:
- **Messages** = raw conversation history (for replay, context)
- **Snapshots** = semantic search targets (for relevance, recommendations)
- Snapshots compress many messages into searchable summaries
- Enables fast vector search without processing thousands of messages

### Q: Why use JSON for embeddings instead of VECTOR type?
**A:** TiDB 7.5+ has experimental VECTOR support, but JSON is more portable and stable for now. Will migrate when VECTOR type is production-ready.

---

## Partitioning Strategy (Colocated Database)

The `ai_memory_colocated` database uses **KEY partitioning** on `(user_id, bot_id)` composite key:

**Tables Partitioned:**
- `sessions`
- `messages`
- `memory_snapshots`
- `usage_stats`

**Benefits:**
- All data for a user-bot pair is physically stored together
- Queries filtered by `(user_id, bot_id)` scan only 1 partition (12.5% of data)
- Reduced cross-partition joins
- Better cache locality

**Trade-offs:**
- Slightly more complex schema (composite primary keys)
- Need to denormalize user_id/bot_id in child tables
- Load distribution depends on user-bot pair distribution

---

## Migration Notes

### From Standard to Colocated Schema

If migrating from `ai_memory` to `ai_memory_colocated`:

```sql
-- Export data from standard schema
SELECT * FROM ai_memory.messages INTO OUTFILE '/tmp/messages.csv';

-- Import to colocated schema (will auto-partition)
LOAD DATA INFILE '/tmp/messages.csv' INTO TABLE ai_memory_colocated.messages;
```

### Adding Vector Index (Future)

When TiDB VECTOR type is stable:

```sql
-- Migrate embedding from JSON to VECTOR
ALTER TABLE memory_snapshots 
ADD COLUMN embedding_vector VECTOR(768);

-- Populate from JSON
UPDATE memory_snapshots 
SET embedding_vector = CAST(embedding AS VECTOR(768));

-- Add vector index
ALTER TABLE memory_snapshots 
ADD VECTOR INDEX idx_embedding (embedding_vector);
```

---

## Related Documentation

- [PLACEMENT_RULES.md](./PLACEMENT_RULES.md) - Data colocation strategy
- [../scripts/README.md](../scripts/README.md) - Data generation and loading
- [../design.md](../design.md) - System architecture
