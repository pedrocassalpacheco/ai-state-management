"""
ChatBot Class

Manages an individual AI bot's conversation logic, memory, and interactions.
"""

import ollama
from typing import List, Dict, Optional
from datetime import datetime

from chatbot.config import CHAT_MODEL, MEMORY_WINDOW_SIZE


class ChatBot:
    """
    AI Chatbot with conversation memory and contextual responses.
    
    Uses Ollama DeepSeek for generating responses with conversation history.
    """
    
    def __init__(self, bot_id: str, bot_name: str, bot_type: str, system_prompt: str):
        """
        Initialize a chatbot instance.
        
        Args:
            bot_id: Unique bot identifier
            bot_name: Display name
            bot_type: Bot category (technical, education, etc.)
            system_prompt: System-level instruction for bot behavior
        """
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.bot_type = bot_type
        self.system_prompt = system_prompt
        self.conversation_history: List[Dict] = []
        
    def add_to_memory(self, role: str, content: str):
        """
        Add a message to conversation memory with sliding window.
        
        Args:
            role: 'user' or 'assistant'
            content: Message content
        """
        self.conversation_history.append({
            'role': role,
            'content': content
        })
        
        # Keep only recent messages (sliding window)
        if len(self.conversation_history) > MEMORY_WINDOW_SIZE:
            self.conversation_history = self.conversation_history[-MEMORY_WINDOW_SIZE:]
    
    def clear_memory(self):
        """Clear conversation history (for new session)."""
        self.conversation_history = []
    
    def generate_response(self, user_message: str, context: Optional[str] = None) -> Dict:
        """
        Generate a contextual response using DeepSeek model.
        
        Args:
            user_message: User's input message
            context: Optional additional context (e.g., chat history summary)
            
        Returns:
            Dict with 'content' and 'tokens' (estimated)
        """
        # Add user message to memory
        self.add_to_memory('user', user_message)
        
        # Build enhanced system prompt with chat history
        enhanced_prompt = self.system_prompt
        if context:
            enhanced_prompt += f"\n\n{context}"
        
        # Build messages for Ollama including system prompt and history
        messages = [
            {'role': 'system', 'content': enhanced_prompt}
        ]
        
        # Add conversation history
        messages.extend(self.conversation_history)
        
        # Generate response
        try:
            response = ollama.chat(
                model=CHAT_MODEL,
                messages=messages
            )
            
            assistant_message = response['message']['content']
            
            # Add bot response to memory
            self.add_to_memory('assistant', assistant_message)
            
            # Estimate tokens (rough approximation)
            tokens = len(assistant_message.split()) * 2
            
            return {
                'content': assistant_message,
                'tokens': tokens,
                'model': CHAT_MODEL
            }
        
        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                'content': "I apologize, I'm having trouble generating a response right now.",
                'tokens': 10,
                'model': CHAT_MODEL
            }
    
    def generate_conversation_starter(self, user_context: str) -> str:
        """
        Generate a natural first message for a user to start the conversation.
        
        Args:
            user_context: Context about what the user wants to ask about
            
        Returns:
            A user question based on bot type and context
        """
        # Use the bot to generate a realistic user question
        prompt = f"""Generate a single, natural opening question that a {user_context} 
would ask a {self.bot_type} assistant. Just provide the question, nothing else.
Keep it conversational and specific to {self.bot_type} topics. Maximum 2 sentences."""
        
        try:
            response = ollama.chat(
                model=CHAT_MODEL,
                messages=[{'role': 'user', 'content': prompt}]
            )
            
            question = response['message']['content'].strip()
            # Remove quotes if model added them
            question = question.strip('"').strip("'")
            
            return question
        
        except Exception as e:
            # Fallback to generic question
            print(f"⚠️  Could not generate starter, using fallback: {e}")
            return f"Hi! Can you help me with something related to {self.bot_type}?"
    
    def get_conversation_summary(self) -> str:
        """
        Get a summary of the current conversation.
        
        Returns:
            Summary string of the conversation history
        """
        if not self.conversation_history:
            return "No conversation yet."
        
        user_msgs = [m for m in self.conversation_history if m['role'] == 'user']
        assistant_msgs = [m for m in self.conversation_history if m['role'] == 'assistant']
        
        return f"Conversation with {self.bot_name}: {len(user_msgs)} user messages, {len(assistant_msgs)} bot responses"
    
    def __repr__(self):
        return f"ChatBot(id={self.bot_id}, name={self.bot_name}, type={self.bot_type})"
