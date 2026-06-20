"""Tests for the message dispatch handler (AI + WhatsApp mocked)."""
from app import handler
from app.memory import ConversationMemory
from app.whatsapp import parse_webhook
from tests.conftest import text_payload, image_payload, audio_payload


def _mem():
    return ConversationMemory("sys", max_turns=5)


def test_text_message_flow(fake_ai, fake_wa):
    msg = parse_webhook(text_payload("hello"))
    reply = handler.handle_incoming(msg, _mem())
    assert reply == "AI reply"
    assert fake_wa[0]["message"] == "AI reply"
    assert fake_wa[0]["to"] == "15551230000"


def test_image_message_uses_vision(fake_ai, fake_wa):
    msg = parse_webhook(image_payload(caption="what's this?"))
    reply = handler.handle_incoming(msg, _mem())
    assert reply == "I see a cat."
    assert fake_ai["image"][0][2] == "what's this?"  # caption forwarded


def test_audio_message_transcribes_then_chats(fake_ai, fake_wa):
    msg = parse_webhook(audio_payload())
    reply = handler.handle_incoming(msg, _mem())
    assert "transcribed words" in reply
    assert "AI reply" in reply
    assert len(fake_ai["audio"]) == 1


def test_help_command(fake_ai, fake_wa):
    msg = parse_webhook(text_payload("/help"))
    reply = handler.handle_incoming(msg, _mem())
    assert "assistant" in reply.lower()
    assert fake_ai["text"] == []  # no AI call for a command


def test_reset_command_clears_memory(fake_ai, fake_wa):
    mem = _mem()
    handler.handle_incoming(parse_webhook(text_payload("hello")), mem)
    assert len(mem.history("15551230000")) > 1
    handler.handle_incoming(parse_webhook(text_payload("/reset")), mem)
    assert len(mem.history("15551230000")) == 1  # only system


def test_chat_failure_is_graceful(fake_wa, monkeypatch):
    import app.handler as h
    monkeypatch.setattr(h.ai, "reply_text", lambda hist: (_ for _ in ()).throw(RuntimeError("boom")))
    mem = _mem()
    reply = handler.handle_incoming(parse_webhook(text_payload("hi")), mem)
    assert "try again" in reply.lower()
    # failed user message should have been rolled back
    assert len(mem.history("15551230000")) == 1


def test_duplicate_message_is_skipped(fake_ai, fake_wa):
    mem = _mem()
    payload = text_payload("hello", msg_id="wamid.DUP")
    handler.handle_incoming(parse_webhook(payload), mem)
    assert len(fake_wa) == 1
    # Re-deliver the exact same message id -> skipped, no second send.
    reply = handler.handle_incoming(parse_webhook(payload), mem)
    assert reply == ""
    assert len(fake_wa) == 1


def test_profile_name_is_recorded(fake_ai, fake_wa):
    mem = _mem()
    handler.handle_incoming(parse_webhook(text_payload("hi", name="Alice")), mem)
    assert mem._profiles.get("15551230000") == "Alice"


def test_memory_persists_across_messages(fake_ai, fake_wa):
    mem = _mem()
    handler.handle_incoming(parse_webhook(text_payload("first")), mem)
    handler.handle_incoming(parse_webhook(text_payload("second")), mem)
    hist = mem.history("15551230000")
    contents = [m["content"] for m in hist]
    assert "first" in contents and "second" in contents
