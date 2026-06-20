"""Tests for bounded conversation memory."""
from app.memory import ConversationMemory


def test_system_prompt_always_first():
    mem = ConversationMemory("be helpful", max_turns=5)
    hist = mem.history("u1")
    assert hist[0] == {"role": "system", "content": "be helpful"}


def test_append_and_history():
    mem = ConversationMemory("sys", max_turns=5)
    mem.append("u1", "user", "hi")
    mem.append("u1", "assistant", "hello")
    hist = mem.history("u1")
    assert [m["role"] for m in hist] == ["system", "user", "assistant"]


def test_history_is_trimmed_to_max_turns():
    mem = ConversationMemory("sys", max_turns=2)  # keep 4 messages
    for i in range(10):
        mem.append("u1", "user", f"msg {i}")
        mem.append("u1", "assistant", f"reply {i}")
    hist = mem.history("u1")
    # system + last 4 messages
    assert len(hist) == 5
    assert hist[1]["content"] == "msg 8"
    assert hist[-1]["content"] == "reply 9"


def test_users_are_isolated():
    mem = ConversationMemory("sys")
    mem.append("a", "user", "from a")
    mem.append("b", "user", "from b")
    assert mem.history("a")[1]["content"] == "from a"
    assert len(mem.history("b")) == 2


def test_pop_last_and_reset():
    mem = ConversationMemory("sys")
    mem.append("u", "user", "x")
    mem.pop_last("u")
    assert len(mem.history("u")) == 1  # only system
    mem.append("u", "user", "y")
    mem.reset("u")
    assert len(mem.history("u")) == 1
