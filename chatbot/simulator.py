"""
Conversation Simulator

Orchestrates multi-user, multi-bot conversations with real-time persistence.
"""

import os
import time
import random
import pymysql
from typing import List, Dict

from chatbot.config import (
    BOTS, USER_PERSONAS, NUM_CONVERSATION_TURNS,
    MEMORY_SNAPSHOT_INTERVAL, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD,
    DEFAULT_DATABASE
)
from chatbot.bot import ChatBot
from chatbot.session_manager import SessionManager
from chatbot.message_handler import MessageHandler
from chatbot.memory import ConversationMemory


class ConversationSimulator:
    """
    Simulates realistic conversations between users and AI bots.
    
    Manages multiple concurrent conversations with database persistence.
    """
    
    def __init__(self, database: str = None):
        """
        Initialize conversation simulator.
        
        Args:
            database: Database name (defaults to TIDB_DATABASE env var or ai_memory)
        """
        self.database = database or os.getenv('TIDB_DATABASE', DEFAULT_DATABASE)
        self.connection = None
        self.session_manager = None
        self.message_handler = None
        self.memory_manager = None
        self.bots: Dict[str, ChatBot] = {}
        
    def connect(self):
        """Establish database connection."""
        print(f"\n🔌 Connecting to database: {self.database}")
        
        self.connection = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=self.database,
            cursorclass=pymysql.cursors.DictCursor
        )
        
        # Initialize managers
        self.session_manager = SessionManager(self.connection)
        self.message_handler = MessageHandler(self.connection)
        self.memory_manager = ConversationMemory(self.connection, self.message_handler)
        
        print(f"✓ Connected to {self.database}")
    
    def disconnect(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            print("\n✓ Database connection closed")
    
    def initialize_bots(self):
        """Initialize chatbot instances from config."""
        print("\n🤖 Initializing bots...")
        
        for bot_id, bot_config in BOTS.items():
            bot = ChatBot(
                bot_id=bot_config['bot_id'],
                bot_name=bot_config['bot_name'],
                bot_type=bot_config['bot_type'],
                system_prompt=bot_config['system_prompt']
            )
            self.bots[bot_id] = bot
            print(f"  ✓ {bot.bot_name} ({bot.bot_type})")
        
        print(f"\n✓ Initialized {len(self.bots)} bots")
    
    def simulate_conversation(
        self,
        user_id: str,
        user_name: str,
        user_context: str,
        bot_id: str,
        num_turns: int = NUM_CONVERSATION_TURNS
    ):
        """
        Simulate a conversation between a user and a bot.
        
        Args:
            user_id: User UUID
            user_name: User display name
            user_context: Context for user persona
            bot_id: Bot identifier
            num_turns: Number of conversation turns
        """
        bot = self.bots.get(bot_id)
        if not bot:
            print(f"❌ Bot {bot_id} not found")
            return
        
        print(f"\n{'='*80}")
        print(f"💬 Starting conversation: {user_name} ↔ {bot.bot_name}")
        print(f"{'='*80}")
        
        # Clear bot memory for new conversation
        bot.clear_memory()
        
        # Create session
        session_id = self.session_manager.create_session(
            user_id=user_id,
            bot_id=bot_id,
            session_name=f"{user_name}'s chat with {bot.bot_name}"
        )
        
        # Track messages for snapshot
        message_buffer = []
        
        # Start conversation
        for turn in range(num_turns):
            print(f"\n--- Turn {turn + 1}/{num_turns} ---")
            
            # Generate user question
            if turn == 0:
                # First message - use context to generate starter
                user_message = bot.generate_conversation_starter(user_context)
            else:
                # Follow-up questions based on conversation
                user_message = self._generate_follow_up_question(bot, turn)
            
            print(f"👤 {user_name}: {user_message}")
            
            # Save user message
            user_msg_result = self.message_handler.insert_message_with_embedding(
                session_id=session_id,
                role='user',
                content=user_message,
                user_id=user_id,
                bot_id=bot_id,
                tokens_used=len(user_message.split()) * 2
            )
            
            message_buffer.append({
                'role': 'user',
                'content': user_message,
                'message_id': user_msg_result['message_id']
            })
            
            print(f"  💾 Saved user message (ID: {user_msg_result['message_id']}, embedding: {user_msg_result['embedding_dim']} dims)")
            
            # Update session
            self.session_manager.update_session(
                session_id=session_id,
                message_count_delta=1,
                tokens_delta=len(user_message.split()) * 2
            )
            
            # Small delay for realism
            time.sleep(0.5)
            
            # Generate bot response
            response = bot.generate_response(user_message)
            print(f"🤖 {bot.bot_name}: {response['content'][:200]}{'...' if len(response['content']) > 200 else ''}")
            
            # Save bot message
            bot_msg_result = self.message_handler.insert_message_with_embedding(
                session_id=session_id,
                role='assistant',
                content=response['content'],
                user_id=user_id,
                bot_id=bot_id,
                tokens_used=response['tokens'],
                model=response['model']
            )
            
            message_buffer.append({
                'role': 'assistant',
                'content': response['content'],
                'message_id': bot_msg_result['message_id']
            })
            
            print(f"  💾 Saved bot response (ID: {bot_msg_result['message_id']}, tokens: {response['tokens']}, embedding: {bot_msg_result['embedding_dim']} dims)")
            
            # Update session
            self.session_manager.update_session(
                session_id=session_id,
                message_count_delta=1,
                tokens_delta=response['tokens']
            )
            
            # Create memory snapshot periodically
            if len(message_buffer) >= MEMORY_SNAPSHOT_INTERVAL:
                self.memory_manager.create_snapshot(
                    session_id=session_id,
                    user_id=user_id,
                    bot_id=bot_id,
                    messages=message_buffer,
                    importance_score=random.uniform(0.6, 0.9)
                )
                message_buffer = []  # Clear buffer after snapshot
            
            # Small delay between turns
            time.sleep(0.5)
        
        # Create final snapshot if messages remain
        if message_buffer:
            self.memory_manager.create_snapshot(
                session_id=session_id,
                user_id=user_id,
                bot_id=bot_id,
                messages=message_buffer,
                importance_score=random.uniform(0.6, 0.9)
            )
        
        # Archive session
        self.session_manager.archive_session(session_id)
        
        # Display final stats
        stats = self.session_manager.get_session_stats(session_id)
        print(f"\n{'─'*80}")
        print(f"📊 Session Complete:")
        print(f"   Messages: {stats.get('message_count', 0)}")
        print(f"   Tokens: {stats.get('total_tokens', 0)}")
        print(f"   Duration: {stats.get('started_at')} → {stats.get('last_active_at')}")
        print(f"{'─'*80}")
    
    def _generate_follow_up_question(self, bot: ChatBot, turn_number: int) -> str:
        """
        Generate a follow-up question based on conversation history.
        
        Args:
            bot: ChatBot instance with conversation memory
            turn_number: Current turn number
            
        Returns:
            Follow-up question string
        """
        # Get last bot response from memory
        history = bot.conversation_history
        if len(history) >= 2:
            last_response = history[-1]['content']
            
            # Generate natural follow-up
            prompt = f"""Based on this response: "{last_response[:200]}"
Generate a single natural follow-up question that continues the conversation.
Keep it conversational, specific, and under 2 sentences. Just the question, nothing else."""
            
            try:
                import ollama
                from chatbot.config import CHAT_MODEL
                
                response = ollama.chat(
                    model=CHAT_MODEL,
                    messages=[{'role': 'user', 'content': prompt}]
                )
                
                question = response['message']['content'].strip().strip('"').strip("'")
                return question
            except Exception as e:
                print(f"⚠️  Could not generate follow-up, using template: {e}")
        
        # Fallback templates
        templates = [
            "Can you tell me more about that?",
            "That's interesting! What else should I know?",
            "How would I get started with that?",
            "What are some common mistakes to avoid?",
            "Do you have any specific examples?"
        ]
        return random.choice(templates)
    
    def run_simulation(self, num_users: int = 5):
        """
        Run simulation with N users and bots.
        
        Args:
            num_users: Number of concurrent user conversations
        """
        print("\n" + "="*80)
        print("🚀 AI CHATBOT SIMULATION")
        print("="*80)
        
        # Connect to database
        self.connect()
        
        # Initialize bots
        self.initialize_bots()
        
        # Get user personas
        personas = list(USER_PERSONAS.items())[:num_users]
        
        # Run conversations
        print(f"\n📝 Simulating {num_users} concurrent conversations...")
        
        for idx, (bot_id, persona) in enumerate(personas, 1):
            # Generate user ID
            import uuid
            user_id = str(uuid.uuid4())
            
            # Run conversation
            self.simulate_conversation(
                user_id=user_id,
                user_name=persona['name'],
                user_context=persona['context'],
                bot_id=bot_id,
                num_turns=NUM_CONVERSATION_TURNS
            )
            
            # Delay between conversations
            if idx < len(personas):
                print(f"\n⏳ Waiting before next conversation...")
                time.sleep(2)
        
        # Disconnect
        self.disconnect()
        
        print("\n" + "="*80)
        print("✅ SIMULATION COMPLETE")
        print("="*80)
        print(f"\n📊 Summary:")
        print(f"   Users: {num_users}")
        print(f"   Conversations: {num_users}")
        print(f"   Turns per conversation: {NUM_CONVERSATION_TURNS}")
        print(f"   Total messages: ~{num_users * NUM_CONVERSATION_TURNS * 2}")
        print(f"   Database: {self.database}")
        print(f"\n💡 Check your database to see the results!")


def main():
    """Main entry point for simulation."""
    import sys
    
    # Get database from command line or environment
    database = sys.argv[1] if len(sys.argv) > 1 else None
    num_users = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    simulator = ConversationSimulator(database=database)
    simulator.run_simulation(num_users=num_users)


if __name__ == '__main__':
    main()
