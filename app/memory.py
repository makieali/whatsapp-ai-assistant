"""Per-user conversation memory with bounded history.

The original kept an unbounded dict per phone number, which grows forever. This
store keeps only the last ``max_turns`` user/assistant exchanges (the system
prompt is always preserved), so memory and token usage stay bounded.
"""
from __future__ import annotations

import threading


class ConversationMemory:
    def __init__(self, system_prompt: str, max_turns: int = 12) -> None:
        self._system = {"role": "system", "content": system_prompt}
        self._max_messages = max_turns * 2  # a turn = user + assistant
        self._lock = threading.Lock()
        self._log: dict[str, list[dict]] = {}

    def history(self, user_id: str) -> list[dict]:
        with self._lock:
            return [self._system] + list(self._log.get(user_id, []))

    def append(self, user_id: str, role: str, content) -> None:
        with self._lock:
            log = self._log.setdefault(user_id, [])
            log.append({"role": role, "content": content})
            # Trim oldest, keeping pairs aligned.
            if len(log) > self._max_messages:
                del log[: len(log) - self._max_messages]

    def pop_last(self, user_id: str) -> None:
        """Undo the most recent message (used when the AI call fails)."""
        with self._lock:
            if self._log.get(user_id):
                self._log[user_id].pop()

    def reset(self, user_id: str) -> None:
        with self._lock:
            self._log.pop(user_id, None)

    def reset_all(self) -> None:
        with self._lock:
            self._log.clear()


def build_memory(config):
    """Return a conversation store based on config.

    Uses the SQL-backed store when ``DATABASE_URL`` is set (shared across workers
    and persistent), otherwise the in-process store (great for tests and single
    quick runs). Both expose the same interface, so nothing else changes.
    """
    if getattr(config, "DATABASE_URL", None):
        from app.sql_memory import SqlMemory

        return SqlMemory(config.SYSTEM_PROMPT, config.MAX_HISTORY_TURNS, config.DATABASE_URL)
    return ConversationMemory(config.SYSTEM_PROMPT, config.MAX_HISTORY_TURNS)
