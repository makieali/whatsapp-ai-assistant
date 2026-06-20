"""SQL-backed conversation memory (SQLite or PostgreSQL).

Same interface as :class:`app.memory.ConversationMemory`, but persisted to a
database via a ``DATABASE_URL``. This matters in production: the app runs under
multiple Gunicorn workers, each of which would otherwise hold its own in-process
dict -- so a user's follow-up message could land on a worker that has never seen
the conversation. A shared database gives every worker one durable view of the
history, and it survives restarts.

  DATABASE_URL=sqlite:///conversations.db          # local, zero setup
  DATABASE_URL=postgresql://user:pass@host/db      # production

Only the last ``max_turns`` exchanges are returned, so token usage stays bounded
exactly as before.
"""
from __future__ import annotations

from sqlalchemy import (
    Column, DateTime, Integer, MetaData, String, Table, Text,
    create_engine, delete, func, insert, select,
)

_metadata = MetaData()

messages = Table(
    "messages", _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", String(64), index=True, nullable=False),
    Column("role", String(16), nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)


def _normalize_url(database_url: str) -> str:
    """Use the maintained psycopg (v3) driver for plain postgres URLs."""
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://"):]
    return database_url


class SqlMemory:
    """Drop-in replacement for ConversationMemory backed by a SQL database."""

    def __init__(self, system_prompt: str, max_turns: int = 12,
                 database_url: str = "sqlite:///conversations.db") -> None:
        self._system = {"role": "system", "content": system_prompt}
        self._max_messages = max_turns * 2  # a turn = user + assistant
        # SQLite needs check_same_thread off to be used from Flask threads.
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(
            _normalize_url(database_url), connect_args=connect_args, future=True,
        )
        _metadata.create_all(self._engine)

    def history(self, user_id: str) -> list[dict]:
        """Return the system prompt followed by the last N messages."""
        stmt = (
            select(messages.c.role, messages.c.content)
            .where(messages.c.user_id == user_id)
            .order_by(messages.c.id.desc())
            .limit(self._max_messages)
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).all()
        recent = [{"role": r.role, "content": r.content} for r in reversed(rows)]
        return [self._system] + recent

    def append(self, user_id: str, role: str, content: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(insert(messages).values(
                user_id=user_id, role=role, content=str(content),
            ))

    def pop_last(self, user_id: str) -> None:
        """Undo the most recent message (used when the AI call fails)."""
        with self._engine.begin() as conn:
            last_id = conn.execute(
                select(messages.c.id)
                .where(messages.c.user_id == user_id)
                .order_by(messages.c.id.desc())
                .limit(1)
            ).scalar()
            if last_id is not None:
                conn.execute(delete(messages).where(messages.c.id == last_id))

    def reset(self, user_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(delete(messages).where(messages.c.user_id == user_id))

    def reset_all(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(delete(messages))
