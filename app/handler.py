"""Core dispatch: turn an IncomingMessage into a reply and send it.

Kept independent of Flask so it can be unit-tested directly. It ties together
memory, the AI layer, and the WhatsApp client.
"""
from __future__ import annotations

import logging

from app import ai
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


def handle_incoming(message: IncomingMessage, store) -> str:
    """Produce a reply for one incoming message and send it via WhatsApp.

    ``store`` is a conversation store (in-process or SQL repository). Returns the
    reply text, or "" if the message was a duplicate that we skipped.
    """
    # Idempotency: WhatsApp re-delivers webhooks. Skip anything already handled.
    if message.message_id and store.seen_message(message.message_id):
        logger.info("Skipping duplicate message %s", message.message_id)
        return ""

    store.touch_user(message.from_number, message.profile_name)
    wa.mark_read(message.phone_number_id, message.message_id)
    reply = _build_reply(message, store)
    wa.send_text(message.phone_number_id, message.from_number, reply)
    return reply


def _build_reply(message: IncomingMessage, store) -> str:
    user = message.from_number

    # Slash commands
    command = message.text.strip().lower()
    if command in ("/help", "help"):
        return HELP_TEXT
    if command in ("/reset", "reset"):
        store.reset(user)
        return "✅ Conversation history cleared. Starting fresh!"

    if message.type == "text":
        return _chat(store, user, message.text,
                     wa_message_id=message.message_id, message_type="text")

    if message.type == "image":
        return _image(store, user, message)

    if message.type == "audio":
        return _audio(store, user, message)

    return ("I can read text, photos, and voice notes. "
            "That message type isn't supported yet — try /help.")


def _chat(store, user: str, text: str, *, wa_message_id: str | None = None,
          message_type: str = "text", media_id: str | None = None) -> str:
    store.append(user, "user", text, message_type=message_type,
                 wa_message_id=wa_message_id, media_id=media_id)
    try:
        reply = ai.reply_text(store.history(user))
    except Exception:  # noqa: BLE001
        logger.exception("Chat failed")
        store.pop_last(user)
        return "⚠️ The AI service is busy right now. Please try again in a moment."
    store.append(user, "assistant", reply)
    return reply


def _image(store, user: str, message: IncomingMessage) -> str:
    try:
        image_bytes, mime = wa.fetch_media(message.media_id)
        reply = ai.reply_about_image(store.history(user), image_bytes, mime, message.text)
    except Exception:  # noqa: BLE001
        logger.exception("Image handling failed")
        return "⚠️ I couldn't process that image. Please try again."
    # Record the exchange as text so it stays in context cheaply.
    caption = message.text.strip() or "[photo]"
    store.append(user, "user", f"[sent a photo] {caption}", message_type="image",
                 wa_message_id=message.message_id, media_id=message.media_id)
    store.append(user, "assistant", reply)
    return reply


def _audio(store, user: str, message: IncomingMessage) -> str:
    try:
        audio_bytes, _ = wa.fetch_media(message.media_id)
        transcript = ai.transcribe_audio(audio_bytes)
    except Exception:  # noqa: BLE001
        logger.exception("Transcription failed")
        return "⚠️ I couldn't understand that voice note. Please try again."
    if not transcript:
        return "🔇 That voice note seemed empty. Please try again."
    reply = _chat(store, user, transcript, wa_message_id=message.message_id,
                  message_type="audio", media_id=message.media_id)
    return f'🎙️ _You said:_ "{transcript}"\n\n{reply}'
