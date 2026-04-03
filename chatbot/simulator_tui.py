"""
Conversation Simulator with Text UI

Adds a terminal dashboard around the existing simulation flow.
"""

import random
import time
from datetime import datetime, timedelta
from typing import Optional

from chatbot.config import MEMORY_SNAPSHOT_INTERVAL, NUM_CONVERSATION_TURNS, USER_PERSONAS
from chatbot.simulator import ConversationSimulator
from chatbot.tui_dashboard import SimulationDashboard


class TuiConversationSimulator(ConversationSimulator):
    """Conversation simulator that reports events to a terminal dashboard."""

    def __init__(self, db_type: str = "aurora"):
        super().__init__(db_type=db_type)
        self.dashboard = SimulationDashboard()

    def simulate_conversation(
        self,
        user_id: str,
        user_name: str,
        user_context: str,
        bot_id: str,
        num_turns: int = NUM_CONVERSATION_TURNS,
        conversation_id: int = 0,
        max_messages: Optional[int] = None,
    ):
        """Run one conversation while updating dashboard events."""
        bot = self.bots.get(bot_id)
        if not bot:
            return

        self.dashboard.register_conversation(
            conversation_id=conversation_id,
            user_name=user_name,
            bot_name=bot.bot_name,
            turns_total=num_turns,
        )

        bot.clear_memory()

        session_id = self.session_manager.create_session(
            user_id=user_id,
            bot_id=bot_id,
            session_name=f"{user_name}'s chat with {bot.bot_name}",
        )
        session_start = datetime.now()
        message_buffer = []

        messages_sent = 0
        turn = 0

        while max_messages is None or messages_sent < max_messages:
            time_elapsed = datetime.now() - session_start
            if time_elapsed > timedelta(minutes=5):
                self.session_manager.archive_session(session_id)
                session_id = self.session_manager.create_session(
                    user_id=user_id,
                    bot_id=bot_id,
                    session_name=f"{user_name}'s chat with {bot.bot_name} (continued)",
                )
                session_start = datetime.now()
                bot.clear_memory()
                message_buffer = []
                self.dashboard.update_status(conversation_id, "NEW_SESSION")

            self.dashboard.update_status(conversation_id, f"TURN_{turn + 1}")

            if turn == 0:
                self.dashboard.update_status(conversation_id, "USER_STARTER")
                user_message = bot.generate_conversation_starter(user_context)
            else:
                self.dashboard.update_status(conversation_id, "USER_FOLLOWUP")
                user_message = self._generate_follow_up_question(bot, turn)

            self.dashboard.mark_user_message(conversation_id, user_message)

            time.sleep(random.uniform(1, 3))

            self.dashboard.update_status(conversation_id, "EMBED_DB_USER")
            user_msg_result = self.message_handler.insert_message_with_embedding(
                session_id=session_id,
                role="user",
                content=user_message,
                user_id=user_id,
                bot_id=bot_id,
                tokens_used=len(user_message.split()) * 2,
            )
            self.dashboard.mark_embedding(
                conversation_id,
                role="user",
                embedding_dim=user_msg_result["embedding_dim"],
            )
            self.dashboard.mark_db_write(
                conversation_id,
                role="user",
                message_id=user_msg_result["message_id"],
            )

            message_buffer.append(
                {
                    "role": "user",
                    "content": user_message,
                    "message_id": user_msg_result["message_id"],
                }
            )
            messages_sent += 1

            self.session_manager.update_session(
                session_id=session_id,
                message_count_delta=1,
                tokens_delta=len(user_message.split()) * 2,
            )

            if max_messages is not None and messages_sent >= max_messages:
                break

            chat_history = (
                "\n".join(
                    [
                        f"{msg['role']}: {msg['content'][:100]}..."
                        for msg in bot.conversation_history[-6:]
                    ]
                )
                if bot.conversation_history
                else "No previous messages."
            )

            self.dashboard.update_status(conversation_id, "LLM_RESPONSE")
            response = bot.generate_response(
                user_message,
                context=f"Recent conversation history:\n{chat_history}",
            )
            self.dashboard.mark_llm_response(
                conversation_id,
                tokens=response["tokens"],
                preview=response["content"],
            )

            time.sleep(random.uniform(2, 4))

            self.dashboard.update_status(conversation_id, "EMBED_DB_BOT")
            bot_msg_result = self.message_handler.insert_message_with_embedding(
                session_id=session_id,
                role="assistant",
                content=response["content"],
                user_id=user_id,
                bot_id=bot_id,
                tokens_used=response["tokens"],
                model=response["model"],
            )
            self.dashboard.mark_embedding(
                conversation_id,
                role="assistant",
                embedding_dim=bot_msg_result["embedding_dim"],
            )
            self.dashboard.mark_db_write(
                conversation_id,
                role="assistant",
                message_id=bot_msg_result["message_id"],
            )

            message_buffer.append(
                {
                    "role": "assistant",
                    "content": response["content"],
                    "message_id": bot_msg_result["message_id"],
                }
            )
            messages_sent += 1

            self.session_manager.update_session(
                session_id=session_id,
                message_count_delta=1,
                tokens_delta=response["tokens"],
            )

            if len(message_buffer) >= MEMORY_SNAPSHOT_INTERVAL:
                self.dashboard.update_status(conversation_id, "SNAPSHOT")
                self.memory_manager.create_snapshot(
                    session_id=session_id,
                    user_id=user_id,
                    bot_id=bot_id,
                    messages=message_buffer,
                    importance_score=random.uniform(0.6, 0.9),
                )
                message_buffer = []

            turn += 1

        if message_buffer:
            self.dashboard.update_status(conversation_id, "SNAPSHOT")
            self.memory_manager.create_snapshot(
                session_id=session_id,
                user_id=user_id,
                bot_id=bot_id,
                messages=message_buffer,
                importance_score=random.uniform(0.6, 0.9),
            )

        self.session_manager.archive_session(session_id)
        self.dashboard.finish_conversation(conversation_id)

    def run_simulation(self, num_conversations: int = 5, max_messages: Optional[int] = None):
        """Run random user-bot simulations with dashboard rendering."""
        self.connect()

        db_label = "Aurora" if self.db_type == "aurora" else "TiDB"
        self.dashboard.start(database_label=db_label, target_conversations=num_conversations)

        bot_ids = self.fetch_bots_from_db()

        with self.connection.cursor() as cursor:
            cursor.execute("SELECT user_id, username, email FROM users")
            all_users = cursor.fetchall()

        if not all_users:
            self.dashboard.update_status(0, "NO_USERS")
            self.disconnect()
            return

        for idx in range(num_conversations):
            db_user = random.choice(all_users)
            bot_id = random.choice(bot_ids)
            persona = random.choice(list(USER_PERSONAS.values()))

            self.simulate_conversation(
                user_id=db_user["user_id"],
                user_name=db_user["username"],
                user_context=persona["context"],
                bot_id=bot_id,
                num_turns=NUM_CONVERSATION_TURNS,
                conversation_id=idx + 1,
                max_messages=max_messages,
            )

            if idx < num_conversations - 1:
                self.dashboard.update_status(idx + 1, "INTERVAL")
                time.sleep(random.uniform(2, 5))

        self.disconnect()
        self.dashboard.finish()


def main():
    """Entry point for the TUI simulator."""
    import sys

    db_type = sys.argv[1] if len(sys.argv) > 1 else "aurora"
    num_conversations = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    max_messages_arg = sys.argv[3] if len(sys.argv) > 3 else "inf"

    if db_type != "aurora":
        print(f"Invalid database type for TUI mode: {db_type}")
        print("Usage: python -m chatbot.simulator_tui aurora [num_conversations] [max_messages|inf]")
        sys.exit(1)

    if max_messages_arg.lower() == "inf":
        max_messages = None
    else:
        max_messages = int(max_messages_arg)
        if max_messages <= 0:
            print("max_messages must be a positive integer or 'inf'")
            sys.exit(1)

    simulator = TuiConversationSimulator(db_type=db_type)
    simulator.run_simulation(
        num_conversations=num_conversations,
        max_messages=max_messages,
    )


if __name__ == "__main__":
    main()
