"""Postgres-specific tests — run only when TEST_DATABASE_URL is set.

CI sets TEST_DATABASE_URL to a real Postgres service so the production driver
path (psycopg) is exercised. Locally the suite skips these unless you opt in:

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/test pytest
"""
import os

import pytest
from sqlalchemy import delete

from app.db import Conversation, Message, SqlRepository, User

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set"
)


@pytest.fixture
def repo():
    r = SqlRepository("be helpful", max_turns=6, database_url=TEST_DATABASE_URL)
    # Start from a clean slate so repeated CI runs are deterministic.
    # Delete in FK-safe order: messages -> conversations -> users.
    with r._Session.begin() as s:
        s.execute(delete(Message))
        s.execute(delete(Conversation))
        s.execute(delete(User))
    return r


def test_full_flow_on_postgres(repo):
    repo.touch_user("999000111", "Sara")
    repo.append("999000111", "user", "My name is Sara", wa_message_id="pg.1")
    repo.append("999000111", "assistant", "Hi Sara!")

    # A second connection (like another worker) sees the same data.
    other = SqlRepository("be helpful", database_url=TEST_DATABASE_URL)
    hist = other.history("999000111")
    assert any(m["content"] == "My name is Sara" for m in hist)

    assert other.seen_message("pg.1") is True
    stats = other.stats()
    assert stats["users"] >= 1 and stats["messages"] >= 2


def test_conversation_reset_on_postgres(repo):
    repo.append("888", "user", "old", wa_message_id="pg.2")
    repo.reset("888")
    repo.append("888", "user", "new", wa_message_id="pg.3")
    contents = [m["content"] for m in repo.history("888")]
    assert "new" in contents and "old" not in contents
