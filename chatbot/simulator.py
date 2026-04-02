"""
Conversation Simulator

Orchestrates multi-user, multi-bot conversations with real-time persistence.
"""

import os
import time
import random
import pymysql
from typing import List, Dict
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

# Import bot configurations from config.py
from chatbot.config import (
    USER_PERSONAS, NUM_CONVERSATION_TURNS,
    MEMORY_SNAPSHOT_INTERVAL
)
from chatbot.bot import ChatBot
from chatbot.session_manager import SessionManager
from chatbot.message_handler import MessageHandler
from chatbot.memory import ConversationMemory
from datetime import datetime, timedelta

# Database configuration from environment
# Aurora RDS MySQL
AURORA_HOST = os.getenv("AURORA_HOST")
AURORA_PORT = int(os.getenv("AURORA_PORT", "3306"))
AURORA_USER = os.getenv("AURORA_USER", "admin")
AURORA_PASSWORD = os.getenv("AURORA_PASSWORD", "")
AURORA_DATABASE = os.getenv("AURORA_DATABASE", "ai_state_management")

# TiDB
TIDB_HOST = os.getenv("TIDB_HOST", "127.0.0.1")
TIDB_PORT = int(os.getenv("TIDB_PORT", "3306"))
TIDB_USER = os.getenv("TIDB_USER", "root")
TIDB_PASSWORD = os.getenv("TIDB_PASSWORD", "")
TIDB_DATABASE = os.getenv("TIDB_DATABASE", "ai_state_management")


class ConversationSimulator:
    """
    Simulates realistic conversations between users and AI bots.
    
    Manages multiple concurrent conversations with database persistence.
    """
    
    def __init__(self, db_type: str = 'aurora'):
        """
        Initialize conversation simulator.
        
        Args:
            db_type: Database type - 'aurora' or 'tidb' (defaults to 'aurora')
        """
        self.db_type = db_type
        
        # Set connection parameters based on database type
        if db_type == 'tidb':
            self.host = TIDB_HOST
            self.port = TIDB_PORT
            self.user = TIDB_USER
            self.password = TIDB_PASSWORD
            self.database = TIDB_DATABASE
        else:  # aurora (default)
            self.host = AURORA_HOST
            self.port = AURORA_PORT
            self.user = AURORA_USER
            self.password = AURORA_PASSWORD
            self.database = AURORA_DATABASE
        
        self.connection = None
        self.session_manager = None
        self.message_handler = None
        self.memory_manager = None
        self.bots: Dict[str, ChatBot] = {}
        
    def connect(self):
        """Establish database connection."""
        db_label = "Aurora RDS MySQL" if self.db_type == 'aurora' else "TiDB"
        print(f"\n🔌 Connecting to {db_label}: {self.database}")
        
        if not self.host:
            raise ValueError(f"{self.db_type.upper()}_HOST not set in environment variables. Check your .env file.")
        
        self.connection = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
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
    
    def fetch_bots_from_db(self):
        """Fetch active bots from database."""
        print("\n🤖 Fetching bots from database...")
        
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT bot_id, bot_name, bot_type, system_prompt 
                FROM bots 
                WHERE is_active = 1
            """)
            db_bots = cursor.fetchall()
        
        if not db_bots:
            raise ValueError("No active bots found in database!")
        
        for bot_data in db_bots:
            bot = ChatBot(
                bot_id=bot_data['bot_id'],
                bot_name=bot_data['bot_name'],
                bot_type=bot_data['bot_type'],
                system_prompt=bot_data['system_prompt']
            )
            self.bots[bot_data['bot_id']] = bot
            print(f"  ✓ {bot.bot_name} ({bot.bot_type})")
        
        print(f"\n✓ Loaded {len(self.bots)} active bots")
        return list(self.bots.keys())
    
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
        
        # Session management with 5-minute expiry
        session_id = self.session_manager.create_session(
            user_id=user_id,
            bot_id=bot_id,
            session_name=f"{user_name}'s chat with {bot.bot_name}"
        )
        session_start = datetime.now()
        
        # Track messages for snapshot
        message_buffer = []
        
        # Start conversation
        for turn in range(num_turns):
            # Check if session should expire (5 minutes)
            time_elapsed = datetime.now() - session_start
            if time_elapsed > timedelta(minutes=5):
                print(f"\n⏰ Session expired after {time_elapsed.seconds//60} minutes - creating new session")
                # Archive old session
                self.session_manager.archive_session(session_id)
                # Create new session
                session_id = self.session_manager.create_session(
                    user_id=user_id,
                    bot_id=bot_id,
                    session_name=f"{user_name}'s chat with {bot.bot_name} (continued)"
                )
                session_start = datetime.now()
                bot.clear_memory()  # Clear history for new session
                message_buffer = []
            
            print(f"\n--- Turn {turn + 1}/{num_turns} ---")
            
            # Generate user question
            if turn == 0:
                # First message - use context to generate starter
                user_message = bot.generate_conversation_starter(user_context)
            else:
                # Follow-up questions based on conversation
                user_message = self._generate_follow_up_question(bot, turn)
            
            print(f"👤 {user_name}: {user_message}")
            
            # Simulate typing delay (1-3 seconds)
            time.sleep(random.uniform(1, 3))
            
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
            
            # Build context with chat history for bot response
            chat_history = "\n".join([
                f"{msg['role']}: {msg['content'][:100]}..."
                for msg in bot.conversation_history[-6:]  # Last 3 exchanges
            ]) if bot.conversation_history else "No previous messages."
            
            # Generate bot response with history context
            response = bot.generate_response(
                user_message,
                context=f"Recent conversation history:\n{chat_history}"
            )
            print(f"🤖 {bot.bot_name}: {response['content'][:200]}{'...' if len(response['content']) > 200 else ''}")
            
            # Simulate bot typing delay (2-4 seconds)
            time.sleep(random.uniform(2, 4))
            
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
    
    def run_simulation(self, num_conversations: int = 5):
        """
        Run simulation with random user-bot pairings.
        
        Args:
            num_conversations: Number of conversations to simulate
        """
        print("\n" + "="*80)
        print("🚀 AI CHATBOT SIMULATION")
        print("="*80)
        
        # Connect to database
        self.connect()
        
        # Fetch bots from database
        bot_ids = self.fetch_bots_from_db()
        
        # Fetch all users from database
        print(f"\n👥 Fetching users from database...")
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT user_id, username, email FROM users")
            all_users = cursor.fetchall()
        
        if not all_users:
            print("❌ No users found in database!")
            print("\nPlease run: make load-data-aurora")
            self.disconnect()
            return
        
        print(f"✓ Found {len(all_users)} users")
        print(f"✓ Found {len(bot_ids)} bots")
        
        # Run conversations with random pairings
        print(f"\n📝 Simulating {num_conversations} conversations with random user-bot pairings...")
        
        for idx in range(num_conversations):
            # Randomly select user and bot
            db_user = random.choice(all_users)
            bot_id = random.choice(bot_ids)
            
            # Get random persona context for variety
            persona = random.choice(list(USER_PERSONAS.values()))
            
            user_id = db_user['user_id']
            user_name = db_user['username']
            bot_name = self.bots[bot_id].bot_name
            
            print(f"\n--- Conversation {idx + 1}/{num_conversations} ---")
            print(f"👤 User: {user_name} ({db_user['email']})")
            print(f"🤖 Bot: {bot_name} ({bot_id})")
            
            # Run conversation
            self.simulate_conversation(
                user_id=user_id,
                user_name=user_name,
                user_context=persona['context'],
                bot_id=bot_id,
                num_turns=NUM_CONVERSATION_TURNS
            )
            
            # Delay between conversations
            if idx < num_conversations - 1:
                delay = random.uniform(2, 5)
                print(f"\n⏳ Waiting {delay:.1f}s before next conversation...")
                time.sleep(delay)
        
        # Disconnect
        self.disconnect()
        
        print("\n" + "="*80)
        print("✅ SIMULATION COMPLETE")
        print("="*80)
        print(f"\n📊 Summary:")
        print(f"   Conversations: {num_conversations}")
        print(f"   Available Users: {len(all_users)}")
        print(f"   Available Bots: {len(bot_ids)}")
        print(f"   Turns per conversation: {NUM_CONVERSATION_TURNS}")
        print(f"   Total messages: ~{num_conversations * NUM_CONVERSATION_TURNS * 2}")
        print(f"   Database: {self.database}")
        print(f"   Session Expiry: 5 minutes")
        print(f"\n💡 Check your database to see the results!")


def main():
    """Main entry point for simulation."""
    import sys
    
    # Parse command line arguments
    # Usage: python -m chatbot.simulator [aurora|tidb] [num_conversations]
    db_type = sys.argv[1] if len(sys.argv) > 1 else 'aurora'
    num_conversations = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    if db_type not in ['aurora', 'tidb']:
        print(f"❌ Invalid database type: {db_type}")
        print("Usage: python -m chatbot.simulator [aurora|tidb] [num_conversations]")
        sys.exit(1)
    
    simulator = ConversationSimulator(db_type=db_type)
    simulator.run_simulation(num_conversations=num_conversations)


if __name__ == '__main__':
    main()
