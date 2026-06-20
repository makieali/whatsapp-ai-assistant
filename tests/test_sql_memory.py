"""Tests for the SQL-backed conversation store (uses a temp SQLite file)."""
import pytest

from app.memory import build_memory
from app.sql_memory import SqlMemory, _normalize_url


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{tmp_path/'conv.db'}"


def test_system_prompt_first_and_append(db_url):
    mem = SqlMemory("be helpful", max_turns=5, database_url=db_url)
    mem.append("u1", "user", "hi")
    mem.append("u1", "assistant", "hello")
    hist = mem.history("u1")
    assert hist[0] == {"role": "system", "content": "be helpful"}
    assert [m["role"] for m in hist] == ["system", "user", "assistant"]
    assert hist[1]["content"] == "hi"


def test_history_trimmed_to_max_turns(db_url):
    mem = SqlMemory("sys", max_turns=2, database_url=db_url)  # keep 4 messages
    for i in range(10):
        mem.append("u1", "user", f"msg {i}")
        mem.append("u1", "assistant", f"reply {i}")
    hist = mem.history("u1")
    assert len(hist) == 5  # system + last 4
    assert hist[1]["content"] == "msg 8"
    assert hist[-1]["content"] == "reply 9"


def test_users_isolated(db_url):
    mem = SqlMemory("sys", database_url=db_url)
    mem.append("a", "user", "from a")
    mem.append("b", "user", "from b")
    assert mem.history("a")[1]["content"] == "from a"
    assert len(mem.history("b")) == 2


def test_pop_last_and_reset(db_url):
    mem = SqlMemory("sys", database_url=db_url)
    mem.append("u", "user", "x")
    mem.pop_last("u")
    assert len(mem.history("u")) == 1  # only system
    mem.append("u", "user", "y")
    mem.reset("u")
    assert len(mem.history("u")) == 1


def test_persists_across_instances(db_url):
    """Two SqlMemory objects on the same URL = two workers sharing state."""
    worker_a = SqlMemory("sys", database_url=db_url)
    worker_a.append("u", "user", "remember me")

    worker_b = SqlMemory("sys", database_url=db_url)
    hist = worker_b.history("u")
    assert any(m["content"] == "remember me" for m in hist)


def test_reset_all(db_url):
    mem = SqlMemory("sys", database_url=db_url)
    mem.append("a", "user", "x")
    mem.append("b", "user", "y")
    mem.reset_all()
    assert len(mem.history("a")) == 1
    assert len(mem.history("b")) == 1


# ---- factory ----

class _Cfg:
    SYSTEM_PROMPT = "sys"
    MAX_HISTORY_TURNS = 5
    DATABASE_URL = None


def test_factory_returns_inmemory_without_url():
    from app.memory import ConversationMemory
    assert isinstance(build_memory(_Cfg), ConversationMemory)


def test_factory_returns_sql_with_url(tmp_path):
    class Cfg(_Cfg):
        DATABASE_URL = f"sqlite:///{tmp_path/'f.db'}"
    assert isinstance(build_memory(Cfg), SqlMemory)


def test_normalize_postgres_url_uses_psycopg3():
    assert _normalize_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert _normalize_url("sqlite:///x.db") == "sqlite:///x.db"
    # already-qualified driver is left untouched
    assert _normalize_url("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"
