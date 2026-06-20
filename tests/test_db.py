"""Tests for the SQL repository: schema, lifecycle, idempotency, stats."""
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Conversation, Message, SqlRepository, User
from app.db.repository import normalize_url
from app.memory import build_memory


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{tmp_path/'conv.db'}"


@pytest.fixture
def repo(db_url):
    return SqlRepository("be helpful", max_turns=5, database_url=db_url)


def _count(repo, model):
    with Session(repo._engine) as s:
        return s.scalar(select(func.count(model.id)))


# ---- basic store interface ----

def test_history_starts_with_system_only(repo):
    assert repo.history("1555") == [{"role": "system", "content": "be helpful"}]


def test_append_creates_user_and_conversation(repo):
    repo.append("1555", "user", "hi")
    assert _count(repo, User) == 1
    assert _count(repo, Conversation) == 1
    assert _count(repo, Message) == 1
    hist = repo.history("1555")
    assert hist[1] == {"role": "user", "content": "hi"}


def test_history_trimmed(db_url):
    repo = SqlRepository("sys", max_turns=2, database_url=db_url)  # keep 4 messages
    for i in range(10):
        repo.append("1555", "user", f"msg {i}")
        repo.append("1555", "assistant", f"reply {i}")
    hist = repo.history("1555")
    assert len(hist) == 5  # system + last 4
    assert hist[1]["content"] == "msg 8"


def test_users_isolated(repo):
    repo.append("a", "user", "from a")
    repo.append("b", "user", "from b")
    assert repo.history("a")[1]["content"] == "from a"
    assert len(repo.history("b")) == 2


def test_pop_last(repo):
    repo.append("1555", "user", "x")
    repo.pop_last("1555")
    assert len(repo.history("1555")) == 1


# ---- user tracking ----

def test_touch_user_records_profile_and_count(repo):
    repo.touch_user("1555", "Alice")
    repo.append("1555", "user", "hello")
    with Session(repo._engine) as s:
        user = s.scalar(select(User).where(User.wa_id == "1555"))
        assert user.profile_name == "Alice"
        assert user.message_count == 1
        assert user.created_at is not None


# ---- conversation lifecycle ----

def test_reset_closes_conversation_and_starts_new(repo):
    repo.append("1555", "user", "old message")
    repo.reset("1555")
    # active conversation is gone -> history is just the system prompt
    assert len(repo.history("1555")) == 1
    # new message opens a fresh conversation; old one is preserved
    repo.append("1555", "user", "new message")
    assert _count(repo, Conversation) == 2
    with Session(repo._engine) as s:
        active = s.scalar(select(func.count(Conversation.id)).where(Conversation.is_active.is_(True)))
        assert active == 1
    # history only shows the new conversation
    contents = [m["content"] for m in repo.history("1555")]
    assert "new message" in contents and "old message" not in contents


# ---- idempotency ----

def test_seen_message_dedup(repo):
    assert repo.seen_message("wamid.A") is False
    repo.append("1555", "user", "hi", wa_message_id="wamid.A")
    assert repo.seen_message("wamid.A") is True
    assert repo.seen_message(None) is False


def test_message_type_stored(repo):
    repo.append("1555", "user", "[sent a photo]", message_type="image", wa_message_id="m1")
    with Session(repo._engine) as s:
        m = s.scalar(select(Message).where(Message.wa_message_id == "m1"))
        assert m.message_type == "image"


# ---- stats ----

def test_stats_aggregates(repo):
    repo.append("a", "user", "hi", message_type="text", wa_message_id="m1")
    repo.append("a", "assistant", "hello")
    repo.append("b", "user", "[photo]", message_type="image", wa_message_id="m2")
    stats = repo.stats()
    assert stats["users"] == 2
    assert stats["conversations"] == 2
    assert stats["active_conversations"] == 2
    assert stats["messages"] == 3
    # user text + assistant reply both count as "text"; the photo as "image"
    assert stats["messages_by_type"]["text"] == 2
    assert stats["messages_by_type"]["image"] == 1


# ---- factory + url ----

def test_factory_picks_sql_with_url(db_url):
    class Cfg:
        SYSTEM_PROMPT = "s"
        MAX_HISTORY_TURNS = 5
        DATABASE_URL = db_url
    assert isinstance(build_memory(Cfg), SqlRepository)


def test_factory_inmemory_without_url():
    from app.memory import ConversationMemory

    class Cfg:
        SYSTEM_PROMPT = "s"
        MAX_HISTORY_TURNS = 5
        DATABASE_URL = None
    assert isinstance(build_memory(Cfg), ConversationMemory)


def test_normalize_url():
    assert normalize_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_url("sqlite:///x.db") == "sqlite:///x.db"
    assert normalize_url("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"


def test_persists_across_instances(db_url):
    a = SqlRepository("s", database_url=db_url)
    a.append("u", "user", "remember me", wa_message_id="x")
    b = SqlRepository("s", database_url=db_url)
    assert any(m["content"] == "remember me" for m in b.history("u"))
    assert b.seen_message("x") is True  # dedup is shared too
