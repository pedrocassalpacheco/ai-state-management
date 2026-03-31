# AI Chatbot Simulation - Design Document

## Overview

A complete chatbot simulation system that demonstrates realistic AI conversations with full database persistence, conversation memory management, and vector embeddings.

## Design Goals

1. **Realistic Conversations**: AI-generated questions and contextualized responses
2. **Full Persistence**: All messages, sessions, and memory snapshots stored in database
3. **Conversation Memory**: Bots maintain context using sliding window and memory snapshots
4. **Vector Embeddings**: Every message embedded for semantic search capabilities
5. **Schema Flexibility**: Support both normalized (OLAP) and denormalized (OLTP) schemas
6. **Production-Ready**: Demonstrates patterns for real chatbot systems

## Architecture

```
User Layer
┌──────────────────────────────────────────────────┐
│  User 1   User 2   User 3   User 4   User 5     │
│    ↓        ↓        ↓        ↓        ↓         │
└────┼────────┼────────┼────────┼────────┼─────────┘
     │        │        │        │        │
     
Bot Layer
┌────┼────────┼────────┼────────┼────────┼─────────┐
│  Tech    Tutor   Health  Career Creative         │
│ Support                   Coach   Writer         │
│                                                   │
│  Each Bot:                                        │
│  - System Prompt (personality)                    │
│  - Conversation Memory (last 6 messages)          │
│  - DeepSeek Integration (response generation)     │
└───────────────────────┬───────────────────────────┘
                        │
                        
Persistence Layer
┌───────────────────────┼───────────────────────────┐
│                       │                           │
│  ┌─────────────┐  ┌──▼──────────┐  ┌──────────┐ │
│  │  Session    │  │   Message   │  │  Memory  │ │
│  │  Manager    │  │   Handler   │  │  Manager │ │
│  └──────┬──────┘  └──────┬──────┘  └─────┬────┘ │
│         │                │               │       │
│         └────────────────┼───────────────┘       │
│                          │                       │
└──────────────────────────┼───────────────────────┘
                           │
                           
Database Layer
┌──────────────────────────▼───────────────────────┐
│            TiDB (MySQL Compatible)               │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ sessions │  │ messages │  │ memory_      │  │
│  │          │  │          │  │ snapshots    │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
│                                                  │
│  Supports:                                       │
│  - Normalized Schema   (OLAP/Analytics)          │
│  - Denormalized Schema (OLTP/Transactional)      │
└──────────────────────────────────────────────────┘
```

## Component Details

### 1. ChatBot (`chatbot/bot.py`)

**Responsibility**: Individual bot intelligence and conversation management

**Key Features**:
- Maintains conversation memory (sliding window of 6 messages)
- Generates contextual responses using DeepSeek + conversation history
- Stays in character based on system prompt and bot type
- Can generate realistic user questions for simulation

**Memory Strategy**:
```python
conversation_history = [
    {'role': 'user', 'content': 'Question 1'},
    {'role': 'assistant', 'content': 'Answer 1'},
    {'role': 'user', 'content': 'Question 2'},
    {'role': 'assistant', 'content': 'Answer 2'},
    # ... keeps last 6 messages (sliding window)
]
```

**Response Generation**:
```python
messages = [
    {'role': 'system', 'content': system_prompt},
    ...conversation_history
]
response = ollama.chat(model='deepseek-r1:1.5b', messages=messages)
```

### 2. SessionManager (`chatbot/session_manager.py`)

**Responsibility**: Database session lifecycle management

**Operations**:
- `create_session(user_id, bot_id)` → Creates new session, returns session_id
- `update_session(session_id, messages++, tokens++)` → Updates counters
- `archive_session(session_id)` → Marks session complete
- `get_session_stats(session_id)` → Retrieves metrics

**Database Updates**:
```sql
-- Create
INSERT INTO sessions (session_id, user_id, bot_id, started_at, status, ...)

-- Update (after each message)
UPDATE sessions 
SET message_count = message_count + 1,
    total_tokens = total_tokens + X,
    last_active_at = NOW()
WHERE session_id = ?

-- Archive (conversation ends)
UPDATE sessions 
SET status = 'archived', ended_at = NOW()
WHERE session_id = ?
```

### 3. MessageHandler (`chatbot/message_handler.py`)

**Responsibility**: Message persistence and embedding generation

**Schema Detection**:
Automatically detects whether user_id/bot_id columns exist in messages table:
- **Normalized**: Only inserts `session_id`
- **Denormalized**: Inserts `session_id + user_id + bot_id`

**Embedding Generation**:
```python
embedding = ollama.embeddings(
    model='nomic-embed-text',
    prompt=message_content
)
# Returns 768-dimensional vector
```

**Message Storage**:
```sql
-- Normalized (ai_memory)
INSERT INTO messages (session_id, role, content, tokens_used, ...)

-- Denormalized (ai_memory_colocated)  
INSERT INTO messages (session_id, user_id, bot_id, role, content, tokens_used, ...)
```

### 4. ConversationMemory (`chatbot/memory.py`)

**Responsibility**: Long-term memory via periodic snapshots

**Snapshot Creation** (every 5 messages):
```python
# 1. Generate summary
summary = f"User asked about X, bot explained Y..."

# 2. Extract key facts
key_facts = {
    'user_questions': [q1, q2, q3],
    'bot_responses': [r1, r2, r3],
    'message_count': 5
}

# 3. Generate embedding
embedding = generate_embedding(summary)

# 4. Store snapshot
INSERT INTO memory_snapshots (
    snapshot_id, session_id, user_id, bot_id,
    summary, key_facts, embedding, ...
)
```

**Purpose**:
- Enable semantic search across conversations
- Provide context for future conversations
- Summarize long conversations
- Support RAG (Retrieval Augmented Generation)

### 5. ConversationSimulator (`chatbot/simulator.py`)

**Responsibility**: Orchestrate realistic multi-user conversations

**Simulation Flow**:
```python
for each user:
    1. Create session
    2. Clear bot memory
    3. for each turn (1 to 10):
        a. Generate user question (AI-powered)
        b. Save message + embedding to DB
        c. Generate bot response (with conversation history)
        d. Save response + embedding to DB
        e. Update session metrics
        f. if turn % 5 == 0: create memory snapshot
    4. Archive session
```

**Question Generation**:
- **Turn 1**: Context-based starter ("software developer having installation issues")
- **Turn 2+**: Follow-ups based on bot's last response

## Configuration

### Bot Personalities (`chatbot/config.py`)

Each bot has:
- **bot_id**: Unique identifier
- **bot_name**: Display name
- **bot_type**: Category (technical, education, health, career, creative)
- **system_prompt**: Personality and behavior instructions
- **topics**: List of expertise areas

Example:
```python
"tech-support": {
    "bot_id": "tech-support",
    "bot_name": "TechSupport Assistant",
    "bot_type": "technical",
    "system_prompt": "You are a helpful technical support assistant...",
    "topics": ["software", "hardware", "troubleshooting"]
}
```

### User Personas

Each persona has:
- **name**: User display name
- **context**: Background for question generation
- **question_starters**: Templates for natural questions

Example:
```python
"tech-support": {
    "name": "Alex Chen",
    "context": "software developer having installation issues",
    "question_starters": ["I'm having trouble with", "Can you help me figure out why", ...]
}
```

## Database Schema Support

### Normalized Schema (ai_memory - OLAP)

```sql
CREATE TABLE messages (
    message_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id CHAR(36),  -- Link to session
    role VARCHAR(50),
    content TEXT,
    tokens_used INT,
    ...
);

-- user_id/bot_id retrieved via JOIN:
SELECT m.*, s.user_id, s.bot_id
FROM messages m
JOIN sessions s ON m.session_id = s.session_id;
```

**Optimized for**:
- Analytics queries
- Cross-user reports  
- Ad-hoc exploration
- JOIN operations

### Denormalized Schema (ai_memory_colocated - OLTP)

```sql
CREATE TABLE messages (
    message_id BIGINT AUTO_INCREMENT,
    session_id CHAR(36),
    user_id CHAR(36),      -- Denormalized
    bot_id VARCHAR(100),   -- Denormalized
    role VARCHAR(50),
    content TEXT,
    tokens_used INT,
    PRIMARY KEY (user_id, bot_id, message_id)
) PARTITION BY KEY(user_id, bot_id) PARTITIONS 8;

-- Direct query, no JOIN:
SELECT * FROM messages 
WHERE user_id = ? AND bot_id = ?;
-- Scans only 1 of 8 partitions!
```

**Optimized for**:
- User-specific queries
- Real-time chat APIs
- Low-latency reads
- Partition pruning

## Conversation Flow Example

```
User: Alex Chen
Bot: TechSupport Assistant
Session: abc-123

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Turn 1:
👤 User: "I'm having trouble installing Docker on Ubuntu..."
   └─> Save to DB (message_id: 1001, embedding: 768 dims)
   └─> Update session (messages: 1, tokens: 20)

🤖 Bot: "I'd be happy to help! First, let's check your Ubuntu version..."
   └─> Generated using: system_prompt + conversation_history
   └─> Save to DB (message_id: 1002, embedding: 768 dims)
   └─> Update session (messages: 2, tokens: 165)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Turn 2:
👤 User: "I'm on Ubuntu 22.04. Should I use apt or snap?"
   └─> Generated by AI based on bot's response
   └─> Save to DB (message_id: 1003, embedding: 768 dims)
   └─> Update session (messages: 3, tokens: 180)

🤖 Bot: "Great! For Ubuntu 22.04, I recommend using apt..."
   └─> Save to DB (message_id: 1004, embedding: 768 dims)
   └─> Update session (messages: 4, tokens: 305)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Turn 3:
...after 5 messages...

📸 Memory Snapshot Created:
   - snapshot_id: snap-456
   - summary: "User Alex asked about Docker installation on Ubuntu..."
   - key_facts: {user_questions: [...], bot_responses: [...]}
   - embedding: 768 dimensions
   
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

...continues for 10 turns...

✓ Session Archived
  - Total messages: 20
  - Total tokens: 2,450
  - Memory snapshots: 4
```

## Usage

### Quick Start

```bash
# Run with default settings (5 users, ai_memory database)
make chatbot-sim

# Or directly
python3 -m chatbot.simulator
```

### Specify Database

```bash
# Normalized schema
make chatbot-sim-standard

# Denormalized schema
make chatbot-sim-colocated
```

### Custom Configuration

```bash
# 10 users on specific database
python3 -m chatbot.simulator ai_memory_colocated 10

# With environment variable
TIDB_DATABASE=ai_memory_colocated python3 -m chatbot.simulator
```

## Verification

### Check Sessions
```sql
SELECT * FROM sessions ORDER BY started_at DESC LIMIT 5;
```

### Check Messages
```sql
SELECT 
    m.message_id,
    m.role,
    LEFT(m.content, 50) as preview,
    m.tokens_used,
    m.created_at
FROM messages m
WHERE m.session_id = '<session-id>'
ORDER BY m.created_at;
```

### Check Memory Snapshots
```sql
SELECT 
    snapshot_id,
    LEFT(summary, 100) as summary_preview,
    message_count,
    importance_score,
    JSON_LENGTH(embedding) as embedding_dims
FROM memory_snapshots
ORDER BY created_at DESC
LIMIT 10;
```

### Performance Comparison

```sql
-- Query on normalized DB (requires JOIN)
EXPLAIN SELECT m.* 
FROM messages m
JOIN sessions s ON m.session_id = s.session_id
WHERE s.user_id = 'X' AND s.bot_id = 'Y';

-- Query on denormalized DB (partition pruning!)
EXPLAIN SELECT m.* 
FROM messages m
WHERE m.user_id = 'X' AND m.bot_id = 'Y';
-- Shows: partitions: p3 (only 1 of 8 partitions scanned)
```

## Next Steps

1. **Performance Analysis**: Run simulation on both databases and compare query times
2. **Semantic Search**: Query memory snapshots using embedding similarity
3. **Context Extension**: Retrieve relevant memories to expand bot context window
4. **Multi-Session**: Continue conversations across multiple sessions
5. **Real-time Dashboard**: Build web UI to visualize conversations as they happen
6. **Production Deployment**: Scale to 1000+ concurrent conversations

## Dependencies

```bash
# Python packages
uv add pymysql ollama

# Ollama models
ollama pull deepseek-r1:1.5b
ollama pull nomic-embed-text
```

## Key Insights

1. **Memory Management**: Sliding window (6 msgs) for immediate context + snapshots (every 5 msgs) for long-term memory
2. **AI-Generated Conversations**: Both questions and answers generated by AI = realistic, varied conversations
3. **Schema Flexibility**: Same codebase works with both normalized and denormalized schemas
4. **Production Patterns**: Session lifecycle, message persistence, embedding generation - all production-ready patterns
5. **HTAP Demonstration**: Shows how to use different schemas for different workload types

## Files Created

```
chatbot/
├── __init__.py              ✓ Package initialization
├── config.py                ✓ Bot configs, personas, parameters
├── bot.py                   ✓ ChatBot class with memory
├── session_manager.py       ✓ Session lifecycle management
├── message_handler.py       ✓ Message persistence + embeddings
├── memory.py                ✓ Memory snapshot creation
├── simulator.py             ✓ Main orchestrator
└── README.md                ✓ Complete documentation

Makefile                     ✓ Added chatbot-sim targets
DESIGN.md                    ✓ This document
```

---

**Ready to run!** Execute `make chatbot-sim` to start the simulation.
