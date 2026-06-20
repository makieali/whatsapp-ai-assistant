"""Conversation stores.

Two interchangeable implementations behind one interface:

- :class:`ConversationMemory` -- in-process, zero-dependency. Default for tests
  and single-process local runs.
- :class:`app.db.SqlRepository` -- SQLite/PostgreSQL, shared across workers and
  persistent, with a full users/conversations/messages schema.

``build_memory`` picks between them based on ``config.DATABASE_URL``.
"""
from __future__ import annotations

import threading


class ConversationMemory:
    """In-process bounded history with the same surface as the SQL repository."""

    def __init__(self, system_prompt: str, max_turns: int = 12) -> None:
        self._system = {"role": "system", "content": system_prompt}
        self._max_messages = max_turns * 2  # a turn = user + assistant
        self._lock = threading.Lock()
        self._log: dict[str, list[dict]] = {}
        self._profiles: dict[str, str | None] = {}
        self._seen_ids: set[str] = set()

    # ---- store interface ----

    def touch_user(self, user_id: str, profile_name: str | None = None) -> None:
        with self._lock:
            self._log.setdefault(user_id, [])
            if profile_name:
                self._profiles[user_id] = profile_name

    def seen_message(self, wa_message_id: str | None) -> bool:
        if not wa_message_id:
            return False
        with self._lock:
            return wa_message_id in self._seen_ids

    def history(self, user_id: str) -> list[dict]:
        with self._lock:
            return [self._system] + list(self._log.get(user_id, []))

    def append(self, user_id: str, role: str, content, *,
               message_type: str = "text", wa_message_id: str | None = None,
               media_id: str | None = None) -> None:
        with self._lock:
            log = self._log.setdefault(user_id, [])
            log.append({"role": role, "content": content})
            if wa_message_id:
                self._seen_ids.add(wa_message_id)
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

    Uses the SQL-backed repository when ``DATABASE_URL`` is set (shared across
    workers, persistent, full schema), otherwise the in-process store.
    """
    if getattr(config, "DATABASE_URL", None):
        from app.db import SqlRepository

        return SqlRepository(config.SYSTEM_PROMPT, config.MAX_HISTORY_TURNS, config.DATABASE_URL)
    return ConversationMemory(config.SYSTEM_PROMPT, config.MAX_HISTORY_TURNS)
