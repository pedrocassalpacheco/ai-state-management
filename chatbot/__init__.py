"""
AI Chatbot Simulation System

Simulates realistic conversations between users and AI bots with:
- Real-time message persistence
- Conversation memory management
- Vector embeddings for semantic search
- Session lifecycle tracking
"""

from chatbot.bot import ChatBot
from chatbot.session_manager import SessionManager
from chatbot.message_handler import MessageHandler
from chatbot.memory import ConversationMemory
from chatbot.simulator import ConversationSimulator

__all__ = [
    'ChatBot',
    'SessionManager',
    'MessageHandler',
    'ConversationMemory',
    'ConversationSimulator'
]
