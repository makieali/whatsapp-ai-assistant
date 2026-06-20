"""Core dispatch: turn an IncomingMessage into a reply and send it.

Kept independent of Flask so it can be unit-tested directly. It ties together
memory, the AI layer, and the WhatsApp client.
"""
from __future__ import annotations

import logging

from app import ai
from app.memory import ConversationMemory
from app.whatsapp import client as wa
from app.whatsapp.parser import IncomingMessage

logger = logging.getLogger(__name__)

HELP_TEXT = (
    "👋 I'm an AI assistant on WhatsApp. You can:\n"
    "• Send a *text* message to chat\n"
    "• Send a *photo* (with an optional caption) and I'll describe or answer about it\n"
    "• Send a *voice note* and I'll transcribe and reply\n\n"
    "Commands: /help, /reset"
)


def handle_incoming(message: IncomingMessage, memory: ConversationMemory) -> str:
    """Produce a reply for one incoming message and send it via WhatsApp."""
    wa.mark_read(message.phone_number_id, message.message_id)
    reply = _build_reply(message, memory)
    wa.send_text(message.phone_number_id, message.from_number, reply)
    return reply


def _build_reply(message: IncomingMessage, memory: ConversationMemory) -> str:
    user = message.from_number

    # Slash commands
    command = message.text.strip().lower()
    if command in ("/help", "help"):
        return HELP_TEXT
    if command in ("/reset", "reset"):
        memory.reset(user)
        return "✅ Conversation history cleared."

    if message.type == "text":
        return _chat(memory, user, message.text)

    if message.type == "image":
        return _image(memory, user, message)

    if message.type == "audio":
        return _audio(memory, user, message)

    return ("I can read text, photos, and voice notes. "
            "That message type isn't supported yet — try /help.")


def _chat(memory: ConversationMemory, user: str, text: str) -> str:
    memory.append(user, "user", text)
    try:
        reply = ai.reply_text(memory.history(user))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Chat failed")
        memory.pop_last(user)
        return "⚠️ The AI service is busy right now. Please try again in a moment."
    memory.append(user, "assistant", reply)
    return reply


def _image(memory: ConversationMemory, user: str, message: IncomingMessage) -> str:
    try:
        image_bytes, mime = wa.fetch_media(message.media_id)
        reply = ai.reply_about_image(memory.history(user), image_bytes, mime, message.text)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Image handling failed")
        return "⚠️ I couldn't process that image. Please try again."
    # Record the exchange as text so it stays in context cheaply.
    caption = message.text.strip() or "[photo]"
    memory.append(user, "user", f"[sent a photo] {caption}")
    memory.append(user, "assistant", reply)
    return reply


def _audio(memory: ConversationMemory, user: str, message: IncomingMessage) -> str:
    try:
        audio_bytes, _ = wa.fetch_media(message.media_id)
        transcript = ai.transcribe_audio(audio_bytes)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Transcription failed")
        return "⚠️ I couldn't understand that voice note. Please try again."
    if not transcript:
        return "🔇 That voice note seemed empty. Please try again."
    reply = _chat(memory, user, transcript)
    return f'🎙️ _You said:_ "{transcript}"\n\n{reply}'
