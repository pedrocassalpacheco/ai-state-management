"""
Text UI Dashboard

Provides a lightweight terminal dashboard for chatbot simulations.
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Deque, Dict, Tuple
import os


@dataclass
class ConversationRow:
    """Live row state for one simulated conversation."""

    conversation_id: int
    user_name: str
    bot_name: str
    turns_completed: int
    turns_total: int
    status: str
    tokens: int
    last_update: datetime


class SimulationDashboard:
    """Simple terminal-based dashboard for simulation progress."""

    # (light_color_code, dark_color_code)
    _COLOR_PALETTES = [
        (227, 178),  # yellow
        (117, 33),   # blue
        (157, 28),   # green
        (224, 167),  # orange
        (218, 125),  # pink
        (195, 31),   # cyan
    ]
    _COLOR_RESET = "\033[0m"

    def __init__(self, max_activity_lines: int = 18):
        self._lock = Lock()
        self._rows: Dict[int, ConversationRow] = {}
        self._activity: Deque[str] = deque(maxlen=max_activity_lines)

        self.started_at = datetime.now()
        self.database_label = ""
        self.target_conversations = 0

        self.total_messages = 0
        self.total_tokens = 0
        self.total_llm_calls = 0
        self.total_embedding_calls = 0
        self.total_db_writes = 0

    def start(self, database_label: str, target_conversations: int) -> None:
        """Initialize dashboard metadata and first render."""
        with self._lock:
            self.started_at = datetime.now()
            self.database_label = database_label
            self.target_conversations = target_conversations
            self._activity.clear()
            self._activity.append(
                f"{self._timestamp()} INFO dashboard started for {target_conversations} conversations"
            )
            self._render()

    def register_conversation(
        self,
        conversation_id: int,
        user_name: str,
        bot_name: str,
        turns_total: int,
    ) -> None:
        """Add a new conversation row to the dashboard."""
        with self._lock:
            self._rows[conversation_id] = ConversationRow(
                conversation_id=conversation_id,
                user_name=user_name,
                bot_name=bot_name,
                turns_completed=0,
                turns_total=turns_total,
                status="STARTING",
                tokens=0,
                last_update=datetime.now(),
            )
            self._activity.append(
                f"{self._timestamp()} CONV#{conversation_id} assigned {user_name} -> {bot_name}"
            )
            self._render()

    def update_status(self, conversation_id: int, status: str) -> None:
        """Update conversation state and refresh."""
        with self._lock:
            row = self._rows.get(conversation_id)
            if not row:
                return
            row.status = status
            row.last_update = datetime.now()
            self._render()

    def mark_user_message(self, conversation_id: int, preview: str) -> None:
        """Record a user message event."""
        with self._lock:
            self.total_messages += 1
            preview_text = self._truncate(preview, 72)
            self._activity.append(
                f"{self._timestamp()} CONV#{conversation_id} USER {preview_text}"
            )
            self._render()

    def mark_llm_response(self, conversation_id: int, tokens: int, preview: str) -> None:
        """Record an LLM response event."""
        with self._lock:
            row = self._rows.get(conversation_id)
            if row:
                row.turns_completed += 1
                row.tokens += tokens
                row.last_update = datetime.now()
            self.total_messages += 1
            self.total_tokens += tokens
            self.total_llm_calls += 1
            preview_text = self._truncate(preview, 72)
            self._activity.append(
                f"{self._timestamp()} CONV#{conversation_id} LLM tokens={tokens} {preview_text}"
            )
            self._render()

    def mark_embedding(self, conversation_id: int, role: str, embedding_dim: int) -> None:
        """Record an embedding generation event."""
        with self._lock:
            self.total_embedding_calls += 1
            self._activity.append(
                f"{self._timestamp()} CONV#{conversation_id} EMBED role={role} dim={embedding_dim}"
            )
            self._render()

    def mark_db_write(self, conversation_id: int, role: str, message_id: int) -> None:
        """Record a database write event."""
        with self._lock:
            self.total_db_writes += 1
            self._activity.append(
                f"{self._timestamp()} CONV#{conversation_id} DB role={role} message_id={message_id}"
            )
            self._render()

    def finish_conversation(self, conversation_id: int) -> None:
        """Mark a conversation as completed."""
        with self._lock:
            row = self._rows.get(conversation_id)
            if not row:
                return
            row.status = "COMPLETED"
            row.last_update = datetime.now()
            self._activity.append(
                f"{self._timestamp()} CONV#{conversation_id} completed"
            )
            self._render()

    def finish(self) -> None:
        """Render final state and summary line."""
        with self._lock:
            self._activity.append(f"{self._timestamp()} INFO simulation completed")
            self._render()

    def _render(self) -> None:
        """Draw the full dashboard in terminal."""
        self._clear_screen()

        uptime = datetime.now() - self.started_at
        uptime_text = str(uptime).split(".")[0]

        print("AI Chatbot Simulation Dashboard")
        print("=" * 100)
        print(
            f"Database: {self.database_label} | "
            f"Target conversations: {self.target_conversations} | "
            f"Uptime: {uptime_text}"
        )
        print(
            f"Messages: {self.total_messages} | Tokens: {self.total_tokens} | "
            f"LLM calls: {self.total_llm_calls} | Embedding calls: {self.total_embedding_calls} | "
            f"DB writes: {self.total_db_writes}"
        )
        print("-" * 100)

        header = (
            f"{'ID':<5} {'USER':<20} {'BOT':<24} {'TURNS':<10} "
            f"{'TOKENS':<8} {'STATUS':<12} {'UPDATED':<8}"
        )
        print(header)
        print("-" * 100)

        for conversation_id in sorted(self._rows.keys()):
            row = self._rows[conversation_id]
            turns_text = f"{row.turns_completed}/{row.turns_total}"
            updated_text = row.last_update.strftime("%H:%M:%S")
            print(
                f"{row.conversation_id:<5} "
                f"{self._truncate(row.user_name, 20):<20} "
                f"{self._truncate(row.bot_name, 24):<24} "
                f"{turns_text:<10} "
                f"{row.tokens:<8} "
                f"{row.status:<12} "
                f"{updated_text:<8}"
            )

        if not self._rows:
            print("No active conversations yet.")

        print("-" * 100)
        print("Recent activity")
        print("-" * 100)

        for line in self._activity:
            print(self._colorize_activity_line(line))

    @staticmethod
    def _truncate(text: str, width: int) -> str:
        if len(text) <= width:
            return text
        return text[: max(width - 3, 1)] + "..."

    @staticmethod
    def _color_text(text: str, color_code: int) -> str:
        return f"\033[38;5;{color_code}m{text}{SimulationDashboard._COLOR_RESET}"

    def _get_palette(self, conversation_id: int) -> Tuple[int, int]:
        idx = max(conversation_id - 1, 0) % len(self._COLOR_PALETTES)
        return self._COLOR_PALETTES[idx]

    def _colorize_activity_line(self, line: str) -> str:
        marker = "CONV#"
        marker_idx = line.find(marker)
        if marker_idx < 0:
            return line

        start = marker_idx + len(marker)
        end = start
        while end < len(line) and line[end].isdigit():
            end += 1

        if end == start:
            return line

        conversation_id = int(line[start:end])
        light_color, dark_color = self._get_palette(conversation_id)

        if " USER " in line:
            return self._color_text(line, light_color)
        if " LLM " in line:
            return self._color_text(line, dark_color)
        if " EMBED " in line:
            return self._color_text(line, dark_color)
        if " DB " in line:
            return self._color_text(line, dark_color)

        return self._color_text(line, light_color)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%H:%M:%S")

    @staticmethod
    def _clear_screen() -> None:
        if os.name == "nt":
            os.system("cls")
            return
        print("\033[2J\033[H", end="")
