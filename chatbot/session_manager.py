"""
Session Manager

Handles database session lifecycle: creation, updates, and archival.
"""

import uuid
from datetime import datetime
from typing import Dict, Optional
import pymysql


class SessionManager:
    """
    Manages conversation session lifecycle in the database.
    
    Creates sessions, tracks metrics, and handles updates.
    """
    
    def __init__(self, connection: pymysql.Connection):
        """
        Initialize session manager.
        
        Args:
            connection: PyMySQL database connection
        """
        self.connection = connection
    
    def create_session(self, user_id: str, bot_id: str, session_name: Optional[str] = None) -> str:
        """
        Create a new conversation session.
        
        Args:
            user_id: User UUID
            bot_id: Bot identifier
            session_name: Optional custom session name
            
        Returns:
            session_id: New session UUID
        """
        session_id = str(uuid.uuid4())
        now = datetime.now()
        
        if not session_name:
            session_name = f"Chat with {bot_id}"
        
        with self.connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO sessions 
                (session_id, user_id, bot_id, started_at, last_active_at, 
                 status, message_count, total_tokens, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                session_id,
                user_id,
                bot_id,
                now,
                now,
                'active',
                0,
                0,
                f'{{"session_name": "{session_name}"}}'
            ))
            self.connection.commit()
        
        print(f"✓ Created session {session_id[:8]}... for user {user_id[:8]}... with bot {bot_id}")
        return session_id
    
    def update_session(self, session_id: str, message_count_delta: int = 1, tokens_delta: int = 0):
        """
        Update session metrics after new messages.
        
        Args:
            session_id: Session UUID
            message_count_delta: Number of messages to add
            tokens_delta: Number of tokens to add
        """
        now = datetime.now()
        
        with self.connection.cursor() as cursor:
            cursor.execute("""
                UPDATE sessions 
                SET message_count = message_count + %s,
                    total_tokens = total_tokens + %s,
                    last_active_at = %s
                WHERE session_id = %s
            """, (message_count_delta, tokens_delta, now, session_id))
            self.connection.commit()
    
    def archive_session(self, session_id: str):
        """
        Mark session as archived when conversation ends.
        
        Args:
            session_id: Session UUID
        """
        now = datetime.now()
        
        with self.connection.cursor() as cursor:
            cursor.execute("""
                UPDATE sessions 
                SET status = 'archived',
                    ended_at = %s
                WHERE session_id = %s
            """, (now, session_id))
            self.connection.commit()
        
        print(f"✓ Archived session {session_id[:8]}...")
    
    def get_session_stats(self, session_id: str) -> Dict:
        """
        Retrieve session statistics.
        
        Args:
            session_id: Session UUID
            
        Returns:
            Dict with session stats (message_count, total_tokens, etc.)
        """
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT message_count, total_tokens, status, started_at, last_active_at
                FROM sessions
                WHERE session_id = %s
            """, (session_id,))
            
            result = cursor.fetchone()
            
            if result:
                return {
                    'message_count': result['message_count'],
                    'total_tokens': result['total_tokens'],
                    'status': result['status'],
                    'started_at': result['started_at'],
                    'last_active_at': result['last_active_at']
                }
            else:
                return {}
