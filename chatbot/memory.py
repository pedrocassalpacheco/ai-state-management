"""
Conversation Memory

Manages conversation memory snapshots with embeddings.
"""

import json
import uuid
from datetime import datetime
from typing import List, Dict
import pymysql

from chatbot.message_handler import MessageHandler


class ConversationMemory:
    """
    Manages conversation memory snapshots and long-term memory storage.
    
    Creates periodic snapshots of conversations with embeddings for semantic search.
    """
    
    def __init__(self, connection: pymysql.Connection, message_handler: MessageHandler):
        """
        Initialize conversation memory manager.
        
        Args:
            connection: PyMySQL database connection
            message_handler: MessageHandler instance for embedding generation
        """
        self.connection = connection
        self.message_handler = message_handler
        self._schema_checked = False
        self._has_user_id = False
        self._has_bot_id = False
    
    def _check_schema(self):
        """Check which columns exist in memory_snapshots table (run once)."""
        if self._schema_checked:
            return
        
        with self.connection.cursor() as cursor:
            # Check for user_id column
            cursor.execute("""
                SELECT COUNT(*) as col_count
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'memory_snapshots'
                AND COLUMN_NAME = 'user_id'
            """)
            self._has_user_id = cursor.fetchone()['col_count'] > 0
            
            # Check for bot_id column
            cursor.execute("""
                SELECT COUNT(*) as col_count
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'memory_snapshots'
                AND COLUMN_NAME = 'bot_id'
            """)
            self._has_bot_id = cursor.fetchone()['col_count'] > 0
        
        self._schema_checked = True
    
    def create_snapshot(
        self,
        session_id: str,
        user_id: str,
        bot_id: str,
        messages: List[Dict],
        importance_score: float = 0.5
    ) -> str:
        """
        Create a memory snapshot from recent messages.
        
        Args:
            session_id: Session UUID
            user_id: User UUID
            bot_id: Bot identifier
            messages: List of message dicts to summarize
            importance_score: Importance score (0.0 to 1.0)
            
        Returns:
            snapshot_id: New snapshot UUID
        """
        self._check_schema()
        
        if not messages:
            return None
        
        # Generate summary
        summary = self._generate_summary(messages, bot_id)
        
        # Extract key facts
        key_facts = self._extract_key_facts(messages)
        
        # Generate embedding for summary
        embedding = self.message_handler.generate_embedding(summary)
        embedding_json = json.dumps(embedding)
        
        # Create snapshot
        snapshot_id = str(uuid.uuid4())
        now = datetime.now()
        
        with self.connection.cursor() as cursor:
            if self._has_user_id and self._has_bot_id:
                # Denormalized schema
                cursor.execute("""
                    INSERT INTO memory_snapshots 
                    (snapshot_id, session_id, user_id, bot_id, summary, key_facts, 
                     embedding, created_at, message_count, importance_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    snapshot_id, session_id, user_id, bot_id, summary,
                    json.dumps(key_facts), embedding_json, now,
                    len(messages), importance_score
                ))
            else:
                # Normalized schema
                cursor.execute("""
                    INSERT INTO memory_snapshots 
                    (snapshot_id, session_id, summary, key_facts, 
                     embedding, created_at, message_count, importance_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    snapshot_id, session_id, summary,
                    json.dumps(key_facts), embedding_json, now,
                    len(messages), importance_score
                ))
            
            self.connection.commit()
        
        print(f"  📸 Created memory snapshot {snapshot_id[:8]}... ({len(messages)} messages, {len(embedding)} dim embedding)")
        return snapshot_id
    
    def _generate_summary(self, messages: List[Dict], bot_id: str) -> str:
        """
        Generate a concise summary of messages.
        
        Args:
            messages: List of message dicts
            bot_id: Bot identifier
            
        Returns:
            Summary string
        """
        user_messages = [m for m in messages if m.get('role') == 'user']
        assistant_messages = [m for m in messages if m.get('role') == 'assistant']
        
        # Extract first user question and last assistant response
        first_question = user_messages[0]['content'][:200] if user_messages else ""
        last_response = assistant_messages[-1]['content'][:200] if assistant_messages else ""
        
        summary = f"Conversation with {bot_id}: "
        summary += f"User asked about: {first_question}... "
        summary += f"Bot provided: {last_response}... "
        summary += f"Total messages: {len(messages)}"
        
        return summary[:500]  # Limit summary length
    
    def _extract_key_facts(self, messages: List[Dict]) -> Dict:
        """
        Extract key facts from messages.
        
        Args:
            messages: List of message dicts
            
        Returns:
            Dict of key facts
        """
        user_questions = []
        bot_responses = []
        
        for msg in messages:
            if msg.get('role') == 'user':
                # Extract first sentence of user messages
                content = msg['content'].split('.')[0][:100]
                user_questions.append(content)
            elif msg.get('role') == 'assistant':
                # Extract first sentence of bot responses
                content = msg['content'].split('.')[0][:100]
                bot_responses.append(content)
        
        return {
            'user_questions': user_questions[:3],  # First 3 questions
            'bot_responses': bot_responses[:3],    # First 3 responses
            'message_count': len(messages),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_relevant_memories(
        self,
        user_id: str,
        bot_id: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        Retrieve relevant memory snapshots for user-bot pair.
        
        Args:
            user_id: User UUID
            bot_id: Bot identifier
            limit: Maximum number of snapshots to return
            
        Returns:
            List of memory snapshot dicts
        """
        self._check_schema()
        
        with self.connection.cursor() as cursor:
            if self._has_user_id and self._has_bot_id:
                # Denormalized schema
                cursor.execute("""
                    SELECT snapshot_id, summary, key_facts, message_count, 
                           importance_score, created_at
                    FROM memory_snapshots
                    WHERE user_id = %s AND bot_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (user_id, bot_id, limit))
            else:
                # Normalized schema - need JOIN through sessions
                cursor.execute("""
                    SELECT ms.snapshot_id, ms.summary, ms.key_facts, ms.message_count, 
                           ms.importance_score, ms.created_at
                    FROM memory_snapshots ms
                    JOIN sessions s ON ms.session_id = s.session_id
                    WHERE s.user_id = %s AND s.bot_id = %s
                    ORDER BY ms.created_at DESC
                    LIMIT %s
                """, (user_id, bot_id, limit))
            
            return cursor.fetchall()
