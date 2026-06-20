"""Conversation repository over the ORM schema.

Exposes the same store interface the handler already uses
(``history`` / ``append`` / ``pop_last`` / ``reset``) plus user and idempotency
helpers (``touch_user`` / ``seen_message``) and aggregate ``stats``. All AI/
WhatsApp logic stays unaware of SQL — it only talks to this small surface.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Conversation, Message, User


def normalize_url(database_url: str) -> str:
    """Use the maintained psycopg (v3) driver for plain postgres URLs."""
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://"):]
    return database_url


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class SqlRepository:
    def __init__(self, system_prompt: str, max_turns: int = 12,
                 database_url: str = "sqlite:///conversations.db",
                 create_tables: bool = True) -> None:
        self._system = {"role": "system", "content": system_prompt}
        self._max_messages = max_turns * 2  # a turn = user + assistant
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(
            normalize_url(database_url), connect_args=connect_args, future=True,
        )
        # Convenience for SQLite/quick start. In production, set
        # AUTO_CREATE_TABLES=false and manage the schema with Alembic.
        if create_tables:
            Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(self._engine, expire_on_commit=False)

    # ---- internals ----

    def _get_or_create_user(self, s: Session, wa_id: str,
                            profile_name: Optional[str] = None) -> User:
        user = s.scalar(select(User).where(User.wa_id == wa_id))
        if user is None:
            user = User(wa_id=wa_id, profile_name=profile_name)
            s.add(user)
            s.flush()
        return user

    def _active_conversation(self, s: Session, user: User,
                             create: bool) -> Optional[Conversation]:
        conv = s.scalar(
            select(Conversation).where(
                Conversation.user_id == user.id, Conversation.is_active.is_(True)
            )
        )
        if conv is None and create:
            conv = Conversation(user_id=user.id)
            s.add(conv)
            s.flush()
        return conv

    # ---- store interface ----

    def touch_user(self, wa_id: str, profile_name: Optional[str] = None) -> None:
        with self._Session.begin() as s:
            user = self._get_or_create_user(s, wa_id, profile_name)
            user.last_seen_at = _now()
            if profile_name:
                user.profile_name = profile_name

    def seen_message(self, wa_message_id: Optional[str]) -> bool:
        if not wa_message_id:
            return False
        with self._Session() as s:
            return s.scalar(
                select(Message.id).where(Message.wa_message_id == wa_message_id)
            ) is not None

    def history(self, wa_id: str) -> list[dict]:
        with self._Session() as s:
            user = s.scalar(select(User).where(User.wa_id == wa_id))
            if user is None:
                return [self._system]
            conv = self._active_conversation(s, user, create=False)
            if conv is None:
                return [self._system]
            rows = s.scalars(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.id.desc())
                .limit(self._max_messages)
            ).all()
        recent = [{"role": m.role, "content": m.content} for m in reversed(rows)]
        return [self._system] + recent

    def append(self, wa_id: str, role: str, content: str, *,
               message_type: str = "text", wa_message_id: Optional[str] = None,
               media_id: Optional[str] = None) -> None:
        with self._Session.begin() as s:
            user = self._get_or_create_user(s, wa_id)
            conv = self._active_conversation(s, user, create=True)
            s.add(Message(
                conversation_id=conv.id, user_id=user.id, role=role,
                content=str(content), message_type=message_type,
                wa_message_id=wa_message_id, media_id=media_id,
            ))
            if role == "user":
                user.message_count += 1

    def pop_last(self, wa_id: str) -> None:
        with self._Session.begin() as s:
            user = s.scalar(select(User).where(User.wa_id == wa_id))
            if user is None:
                return
            conv = self._active_conversation(s, user, create=False)
            if conv is None:
                return
            last = s.scalar(
                select(Message).where(Message.conversation_id == conv.id)
                .order_by(Message.id.desc()).limit(1)
            )
            if last is not None:
                s.delete(last)

    def reset(self, wa_id: str) -> None:
        """Close the active conversation; the next message starts a new one."""
        with self._Session.begin() as s:
            user = s.scalar(select(User).where(User.wa_id == wa_id))
            if user is None:
                return
            conv = self._active_conversation(s, user, create=False)
            if conv is not None:
                conv.is_active = False
                conv.ended_at = _now()

    def reset_all(self) -> None:
        with self._Session.begin() as s:
            for conv in s.scalars(select(Conversation).where(Conversation.is_active.is_(True))):
                conv.is_active = False
                conv.ended_at = _now()

    def stats(self) -> dict:
        with self._Session() as s:
            by_type = dict(s.execute(
                select(Message.message_type, func.count(Message.id))
                .group_by(Message.message_type)
            ).all())
            return {
                "users": s.scalar(select(func.count(User.id))) or 0,
                "conversations": s.scalar(select(func.count(Conversation.id))) or 0,
                "active_conversations": s.scalar(
                    select(func.count(Conversation.id)).where(Conversation.is_active.is_(True))
                ) or 0,
                "messages": s.scalar(select(func.count(Message.id))) or 0,
                "messages_by_type": by_type,
            }
