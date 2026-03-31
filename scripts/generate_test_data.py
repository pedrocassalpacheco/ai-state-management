#!/usr/bin/env python3
"""
Generate test dataset for AI State Management system.

Creates realistic conversation data with:
- 100 users
- 15 bots
- Multiple sessions per user
- Multiple messages per session
- Memory snapshots with embeddings (at least 1000)
"""

import json
import random
import uuid
from datetime import datetime, timedelta
import ollama

from config import (
    NUM_USERS, NUM_BOTS, MIN_SESSIONS_PER_USER, MAX_SESSIONS_PER_USER,
    MIN_MESSAGES_PER_SESSION, MAX_MESSAGES_PER_SESSION,
    SNAPSHOT_EVERY_N_MESSAGES, TARGET_SNAPSHOTS, DATA_DIR,
    EMBEDDING_MODEL, EMBEDDING_DIMENSION
)

# Sample data for realistic generation
FIRST_NAMES = [
    "Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry",
    "Iris", "Jack", "Kate", "Liam", "Maya", "Noah", "Olivia", "Peter",
    "Quinn", "Ruby", "Sam", "Tara", "Uma", "Victor", "Wendy", "Xander",
    "Yara", "Zoe", "Alex", "Blake", "Casey", "Drew", "Emerson", "Finley"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"
]

BOT_CONFIGS = [
    {"type": "assistant", "name": "General Assistant", "purpose": "general help"},
    {"type": "support", "name": "Customer Support", "purpose": "customer service"},
    {"type": "sales", "name": "Sales Agent", "purpose": "product sales"},
    {"type": "technical", "name": "Tech Support", "purpose": "technical help"},
    {"type": "education", "name": "Learning Coach", "purpose": "educational guidance"},
    {"type": "health", "name": "Health Advisor", "purpose": "health information"},
    {"type": "finance", "name": "Financial Advisor", "purpose": "financial advice"},
    {"type": "travel", "name": "Travel Assistant", "purpose": "travel planning"},
    {"type": "coding", "name": "Code Helper", "purpose": "programming assistance"},
    {"type": "writing", "name": "Writing Coach", "purpose": "writing improvement"},
    {"type": "language", "name": "Language Tutor", "purpose": "language learning"},
    {"type": "career", "name": "Career Counselor", "purpose": "career guidance"},
    {"type": "legal", "name": "Legal Assistant", "purpose": "legal information"},
    {"type": "creative", "name": "Creative Muse", "purpose": "creative inspiration"},
    {"type": "productivity", "name": "Productivity Coach", "purpose": "productivity tips"}
]

CONVERSATION_TOPICS = {
    "assistant": [
        "How do I create a to-do list?",
        "What's the weather forecast?",
        "Can you help me plan my day?",
        "I need recipe suggestions",
        "How to improve productivity"
    ],
    "support": [
        "My order hasn't arrived",
        "How do I reset my password?",
        "I need to return a product",
        "Account billing question",
        "Feature request"
    ],
    "technical": [
        "My app keeps crashing",
        "Error message troubleshooting",
        "Installation problems",
        "API integration help",
        "Database connection issues"
    ],
    "coding": [
        "Python list comprehension",
        "JavaScript async/await",
        "SQL query optimization",
        "Git merge conflicts",
        "Docker container setup"
    ],
    "education": [
        "Explain quantum physics",
        "Help with calculus homework",
        "History of World War II",
        "Biology cell structure",
        "Chemistry periodic table"
    ]
}

def generate_users(num_users):
    """Generate user data."""
    users = []
    for i in range(num_users):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        username = f"{first.lower()}.{last.lower()}{random.randint(1, 999)}"
        
        user = {
            "user_id": str(uuid.uuid4()),
            "username": username,
            "email": f"{username}@example.com",
            "created_at": (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
            "metadata": json.dumps({
                "first_name": first,
                "last_name": last,
                "preferences": {
                    "language": random.choice(["en", "es", "fr", "de"]),
                    "theme": random.choice(["light", "dark"])
                }
            })
        }
        users.append(user)
    
    return users

def generate_bots():
    """Generate bot configurations."""
    bots = []
    for i, config in enumerate(BOT_CONFIGS):
        bot = {
            "bot_id": f"{config['type']}-bot-{i+1}",
            "bot_name": config["name"],
            "bot_type": config["type"],
            "system_prompt": f"You are a helpful {config['name']} focused on {config['purpose']}.",
            "config": json.dumps({
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2000
            }),
            "is_active": True
        }
        bots.append(bot)
    
    return bots

def generate_conversation_text(bot_type, is_user=True):
    """Generate realistic conversation text."""
    topics = CONVERSATION_TOPICS.get(bot_type, CONVERSATION_TOPICS["assistant"])
    
    if is_user:
        return random.choice(topics)
    else:
        responses = [
            "I'd be happy to help you with that.",
            "Let me explain this step by step.",
            "Here's what I recommend:",
            "That's a great question!",
            "Based on your needs, I suggest:",
            "I understand your concern. Here's what we can do:"
        ]
        return f"{random.choice(responses)} {random.choice(['...', 'Let me provide more details.', 'Would you like me to elaborate?'])}"

def generate_embedding(text):
    """Generate embedding using Ollama."""
    try:
        response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=text)
        return response['embedding']
    except Exception as e:
        print(f"Warning: Failed to generate embedding: {e}")
        # Return zero vector as fallback
        return [0.0] * EMBEDDING_DIMENSION

def generate_sessions_and_messages(users, bots):
    """Generate sessions, messages, and memory snapshots."""
    sessions = []
    messages = []
    snapshots = []
    
    snapshot_count = 0
    
    # Track which bots each user has talked to
    user_bot_history = {user['user_id']: [] for user in users}
    
    for user in users:
        num_sessions = random.randint(MIN_SESSIONS_PER_USER, MAX_SESSIONS_PER_USER)
        
        for _ in range(num_sessions):
            # Pick a bot (prefer bots the user has used before 30% of the time)
            if user_bot_history[user['user_id']] and random.random() < 0.3:
                bot = random.choice(user_bot_history[user['user_id']])
            else:
                bot = random.choice(bots)
                if bot not in user_bot_history[user['user_id']]:
                    user_bot_history[user['user_id']].append(bot)
            
            session_id = str(uuid.uuid4())
            session_start = datetime.now() - timedelta(days=random.randint(0, 180))
            
            session = {
                "session_id": session_id,
                "user_id": user["user_id"],
                "bot_id": bot["bot_id"],
                "started_at": session_start.isoformat(),
                "last_active_at": (session_start + timedelta(minutes=random.randint(5, 120))).isoformat(),
                "status": random.choice(["active", "archived"]),
                "message_count": 0,
                "total_tokens": 0,
                "metadata": json.dumps({
                    "session_name": f"Chat with {bot['bot_name']}",
                    "tags": [bot["bot_type"]]
                })
            }
            
            # Generate messages for this session
            num_messages = random.randint(MIN_MESSAGES_PER_SESSION, MAX_MESSAGES_PER_SESSION)
            session_messages = []
            current_time = session_start
            
            for msg_idx in range(num_messages):
                # Alternate between user and assistant
                is_user = msg_idx % 2 == 0
                role = "user" if is_user else "assistant"
                content = generate_conversation_text(bot["bot_type"], is_user)
                tokens = len(content.split()) * 2  # Rough token estimate
                
                message = {
                    "session_id": session_id,
                    "user_id": user["user_id"],  # Denormalized for partitioning
                    "bot_id": bot["bot_id"],  # Denormalized for partitioning
                    "role": role,
                    "content": content,
                    "created_at": current_time.isoformat(),
                    "tokens_used": tokens,
                    "model": bot["config"] if not is_user else None,
                    "metadata": json.dumps({"message_index": msg_idx})
                }
                
                session_messages.append(message)
                messages.append(message)
                session["message_count"] += 1
                session["total_tokens"] += tokens
                
                current_time += timedelta(seconds=random.randint(10, 300))
                
                # Create memory snapshot every N messages
                if (msg_idx + 1) % SNAPSHOT_EVERY_N_MESSAGES == 0 and snapshot_count < TARGET_SNAPSHOTS:
                    # Get recent messages for summary
                    recent_msgs = session_messages[-SNAPSHOT_EVERY_N_MESSAGES:]
                    summary = f"Discussion about {bot['bot_type']} topics. "
                    summary += f"User asked {len([m for m in recent_msgs if m['role'] == 'user'])} questions. "
                    summary += f"Bot provided {len([m for m in recent_msgs if m['role'] == 'assistant'])} responses."
                    
                    # Generate embedding
                    print(f"Generating embedding for snapshot {snapshot_count + 1}/{TARGET_SNAPSHOTS}...")
                    embedding = generate_embedding(summary)
                    
                    key_facts = {
                        "topics": [bot["bot_type"]],
                        "message_count": len(recent_msgs),
                        "user_questions": [m["content"][:50] for m in recent_msgs if m["role"] == "user"]
                    }
                    
                    snapshot = {
                        "snapshot_id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "user_id": user["user_id"],
                        "bot_id": bot["bot_id"],
                        "summary": summary,
                        "key_facts": json.dumps(key_facts),
                        "embedding": json.dumps(embedding),
                        "created_at": current_time.isoformat(),
                        "message_count": len(recent_msgs),
                        "importance_score": random.uniform(0.3, 1.0),
                        "topics": json.dumps([bot["bot_type"], "conversation"]),
                        "entities": json.dumps({"bot": bot["bot_name"], "user": user["username"]})
                    }
                    
                    snapshots.append(snapshot)
                    snapshot_count += 1
                    
                    if snapshot_count >= TARGET_SNAPSHOTS:
                        break
            
            sessions.append(session)
            
            if snapshot_count >= TARGET_SNAPSHOTS:
                break
        
        if snapshot_count >= TARGET_SNAPSHOTS:
            print(f"\nReached target of {TARGET_SNAPSHOTS} snapshots!")
            break
    
    return sessions, messages, snapshots

def save_jsonl(data, filename):
    """Save data to JSONL file."""
    filepath = DATA_DIR / filename
    with open(filepath, 'w') as f:
        for item in data:
            f.write(json.dumps(item) + '\n')
    print(f"✓ Saved {len(data)} records to {filepath}")

def main():
    """Generate all test data."""
    print("=" * 60)
    print("Generating Test Dataset for AI State Management")
    print("=" * 60)
    
    # Create output directory
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate data
    print("\n1. Generating users...")
    users = generate_users(NUM_USERS)
    save_jsonl(users, "users.jsonl")
    
    print("\n2. Generating bots...")
    bots = generate_bots()
    save_jsonl(bots, "bots.jsonl")
    
    print("\n3. Generating sessions, messages, and memory snapshots...")
    print("   (This will take a few minutes to generate embeddings)")
    sessions, messages, snapshots = generate_sessions_and_messages(users, bots)
    save_jsonl(sessions, "sessions.jsonl")
    save_jsonl(messages, "messages.jsonl")
    save_jsonl(snapshots, "memory_snapshots.jsonl")
    
    # Summary
    print("\n" + "=" * 60)
    print("Dataset Generation Complete!")
    print("=" * 60)
    print(f"Users:            {len(users)}")
    print(f"Bots:             {len(bots)}")
    print(f"Sessions:         {len(sessions)}")
    print(f"Messages:         {len(messages)}")
    print(f"Memory Snapshots: {len(snapshots)}")
    print(f"\nFiles saved to: {DATA_DIR.absolute()}")
    print("=" * 60)

if __name__ == "__main__":
    main()
