"""
Chatbot Configuration

Defines bot personalities, system prompts, and simulation parameters.

Supports dual database architecture:
- Aurora RDS MySQL: ai_memory (non-partitioned, OLAP/Analytics)
- TiDB: ai_memory_colocated (partitioned, OLTP/Transactional)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file (project root)
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

# Ollama Models
CHAT_MODEL = "deepseek-r1:1.5b"
EMBEDDING_MODEL = "nomic-embed-text"

# Aurora RDS MySQL Configuration (for ai_memory - non-partitioned)
AURORA_HOST = os.getenv("AURORA_HOST", None)
AURORA_PORT = int(os.getenv("AURORA_PORT", "3306"))
AURORA_USER = os.getenv("AURORA_USER", "admin")
AURORA_PASSWORD = os.getenv("AURORA_PASSWORD", "")
AURORA_DATABASE = os.getenv("AURORA_DATABASE", "ai_state_management")  # Non-partitioned database

# TiDB Configuration (for ai_memory_colocated - partitioned)
TIDB_HOST = os.getenv("TIDB_HOST", "127.0.0.1")
TIDB_PORT = int(os.getenv("TIDB_PORT", "3306"))
TIDB_USER = os.getenv("TIDB_USER", "root")
TIDB_PASSWORD = os.getenv("TIDB_PASSWORD", "")
TIDB_DATABASE = os.getenv("TIDB_DATABASE", "ai_state_management")  # Partitioned database

# Simulation Parameters
NUM_CONVERSATION_TURNS = 10  # Messages per conversation (user + bot = 2 turns)
MEMORY_SNAPSHOT_INTERVAL = 5  # Create snapshot every N messages
MEMORY_WINDOW_SIZE = 6  # Number of recent messages to keep in context

# Bot Configurations
BOTS = {
    "tech-support": {
        "bot_id": "tech-support",
        "bot_name": "TechSupport Assistant",
        "bot_type": "technical",
        "system_prompt": """You are a helpful technical support assistant. 
You help users troubleshoot software and hardware issues, provide step-by-step solutions,
and explain technical concepts in simple terms. Be patient, clear, and solution-focused.
Ask clarifying questions when needed.""",
        "topics": ["software", "hardware", "troubleshooting", "installation", "configuration"]
    },
    
    "learning-tutor": {
        "bot_id": "learning-tutor",
        "bot_name": "Learning Tutor",
        "bot_type": "education",
        "system_prompt": """You are an encouraging educational tutor.
You help students learn new concepts by breaking them down into simple steps.
Use analogies, examples, and encourage questions. Adapt your explanations to the
student's level of understanding. Be patient and supportive.""",
        "topics": ["math", "science", "programming", "languages", "study tips"]
    },
    
    "health-advisor": {
        "bot_id": "health-advisor",
        "bot_name": "Health & Wellness Advisor",
        "bot_type": "health",
        "system_prompt": """You are a knowledgeable health and wellness advisor.
You provide general information about healthy lifestyle choices, exercise, nutrition,
and mental wellbeing. Always remind users to consult healthcare professionals for
medical advice. Be encouraging and focus on sustainable habits.""",
        "topics": ["exercise", "nutrition", "sleep", "stress management", "healthy habits"]
    },
    
    "career-coach": {
        "bot_id": "career-coach",
        "bot_name": "Career Coach",
        "bot_type": "career",
        "system_prompt": """You are an experienced career coach and mentor.
You help people with job searching, resume building, interview preparation,
career transitions, and professional development. Provide actionable advice,
be motivating, and ask insightful questions to understand their goals.""",
        "topics": ["job search", "resume", "interviews", "career growth", "networking"]
    },
    
    "creative-writer": {
        "bot_id": "creative-writer",
        "bot_name": "Creative Writing Assistant",
        "bot_type": "creative",
        "system_prompt": """You are a creative writing assistant and storyteller.
You help people develop story ideas, create characters, improve their writing style,
and overcome writer's block. Be imaginative, encouraging, and provide constructive
feedback. Ask about their vision and help bring it to life.""",
        "topics": ["storytelling", "characters", "plot", "world-building", "writing tips"]
    }
}

# User Simulation Personas
# These help generate realistic user questions based on context
USER_PERSONAS = {
    "tech-support": {
        "name": "Alex Chen",
        "context": "software developer having installation issues",
        "question_starters": [
            "I'm having trouble with",
            "Can you help me figure out why",
            "I keep getting an error when",
            "How do I fix",
            "What's the best way to"
        ]
    },
    
    "learning-tutor": {
        "name": "Sarah Martinez",
        "context": "college student learning programming",
        "question_starters": [
            "I don't understand",
            "Can you explain",
            "What's the difference between",
            "How does",
            "Why do we need"
        ]
    },
    
    "health-advisor": {
        "name": "Mike Johnson",
        "context": "professional looking to improve fitness",
        "question_starters": [
            "What's a good way to",
            "I want to start",
            "How often should I",
            "Is it better to",
            "What are some tips for"
        ]
    },
    
    "career-coach": {
        "name": "Emily Rodriguez",
        "context": "mid-level professional seeking career growth",
        "question_starters": [
            "I'm thinking about",
            "How can I improve my",
            "What should I include in my",
            "Do you have advice on",
            "What's the best approach for"
        ]
    },
    
    "creative-writer": {
        "name": "Jordan Lee",
        "context": "aspiring novelist working on first book",
        "question_starters": [
            "I'm stuck on",
            "How do I develop",
            "What makes a good",
            "I'm not sure how to",
            "Can you help me with"
        ]
    }
}
