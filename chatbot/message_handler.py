"""
Message Handler

Manages message persistence and embedding generation.
"""

import json
from datetime import datetime
from typing import Dict, Optional
import pymysql
import ollama

from chatbot.config import EMBEDDING_MODEL


class MessageHandler:
    """
    Handles message storage and embedding generation.
    
    Supports both normalized and denormalized schemas.
    """
    
    def __init__(self, connection: pymysql.Connection):
        """
        Initialize message handler.
        
        Args:
            connection: PyMySQL database connection
        """
        self.connection = connection
        self._schema_checked = False
        self._has_user_id = False
        self._has_bot_id = False
    
    def _check_schema(self):
        """Check which columns exist in messages table (run once)."""
        if self._schema_checked:
            return
        
        with self.connection.cursor() as cursor:
            # Check for user_id column
            cursor.execute("""
                SELECT COUNT(*) as col_count
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'messages'
                AND COLUMN_NAME = 'user_id'
            """)
            self._has_user_id = cursor.fetchone()['col_count'] > 0
            
            # Check for bot_id column
            cursor.execute("""
                SELECT COUNT(*) as col_count
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'messages'
                AND COLUMN_NAME = 'bot_id'
            """)
            self._has_bot_id = cursor.fetchone()['col_count'] > 0
        
        self._schema_checked = True
        
        schema_type = "denormalized (OLTP)" if (self._has_user_id and self._has_bot_id) else "normalized (OLAP)"
        print(f"ℹ️  Detected {schema_type} schema for messages table")
    
    def insert_message(
        self,
        session_id: str,
        role: str,
        content: str,
        user_id: Optional[str] = None,
        bot_id: Optional[str] = None,
        tokens_used: int = 0,
        model: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> int:
        """
        Insert a message into the database.
        
        Args:
            session_id: Session UUID
            role: 'user' or 'assistant'
            content: Message text
            user_id: User UUID (for denormalized schema)
            bot_id: Bot identifier (for denormalized schema)
            tokens_used: Token count
            model: Model name if assistant message
            metadata: Optional metadata dict
            
        Returns:
            message_id: Inserted message ID
        """
        self._check_schema()
        
        now = datetime.now()
        metadata_json = json.dumps(metadata) if metadata else None
        
        with self.connection.cursor() as cursor:
            if self._has_user_id and self._has_bot_id:
                # Denormalized schema (ai_memory_colocated)
                cursor.execute("""
                    INSERT INTO messages 
                    (session_id, user_id, bot_id, role, content, created_at, tokens_used, model, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (session_id, user_id, bot_id, role, content, now, tokens_used, model, metadata_json))
            else:
                # Normalized schema (ai_memory)
                cursor.execute("""
                    INSERT INTO messages 
                    (session_id, role, content, created_at, tokens_used, model, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (session_id, role, content, now, tokens_used, model, metadata_json))
            
            self.connection.commit()
            message_id = cursor.lastrowid
        
        return message_id
    
    def generate_embedding(self, text: str) -> list:
        """
        Generate vector embedding for text using Ollama.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats (embedding vector)
        """
        try:
            response = ollama.embeddings(
                model=EMBEDDING_MODEL,
                prompt=text
            )
            return response['embedding']
        except Exception as e:
            print(f"⚠️  Error generating embedding: {e}")
            return []
    
    def insert_message_with_embedding(
        self,
        session_id: str,
        role: str,
        content: str,
        user_id: Optional[str] = None,
        bot_id: Optional[str] = None,
        tokens_used: int = 0,
        model: Optional[str] = None
    ) -> Dict:
        """
        Insert message and generate its embedding.
        
        Args:
            session_id: Session UUID
            role: 'user' or 'assistant'
            content: Message text
            user_id: User UUID (for denormalized schema)
            bot_id: Bot identifier (for denormalized schema)
            tokens_used: Token count
            model: Model name if assistant message
            
        Returns:
            Dict with message_id and embedding
        """
        # Generate embedding
        embedding = self.generate_embedding(content)
        
        # Store embedding in metadata
        metadata = {
            'embedding_model': EMBEDDING_MODEL,
            'embedding_dim': len(embedding),
            'has_embedding': len(embedding) > 0
        }
        
        # Insert message
        message_id = self.insert_message(
            session_id=session_id,
            role=role,
            content=content,
            user_id=user_id,
            bot_id=bot_id,
            tokens_used=tokens_used,
            model=model,
            metadata=metadata
        )
        
        return {
            'message_id': message_id,
            'embedding': embedding,
            'embedding_dim': len(embedding)
        }
    
    def get_session_messages(self, session_id: str, limit: int = 50) -> list:
        """
        Retrieve messages for a session.
        
        Args:
            session_id: Session UUID
            limit: Maximum number of messages to return
            
        Returns:
            List of message dicts
        """
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT message_id, role, content, created_at, tokens_used, model
                FROM messages
                WHERE session_id = %s
                ORDER BY created_at ASC
                LIMIT %s
            """, (session_id, limit))
            
            return cursor.fetchall()
