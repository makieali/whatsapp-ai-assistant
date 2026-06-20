"""Parse WhatsApp Cloud API webhook payloads into a normalized message.

The raw payload is deeply nested and easy to crash on. ``parse_webhook`` returns
a single ``IncomingMessage`` (or ``None`` for non-message events such as status
callbacks), so the rest of the app never touches the raw structure.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class IncomingMessage:
    from_number: str
    phone_number_id: str
    message_id: str
    type: str                       # text | image | audio | unsupported
    text: str = ""                  # text body, or image caption
    media_id: Optional[str] = None  # for image/audio
    profile_name: Optional[str] = None  # WhatsApp contact display name


def parse_webhook(body: dict) -> Optional[IncomingMessage]:
    """Extract the first user message, or None if this isn't a message event."""
    if not isinstance(body, dict) or body.get("object") != "whatsapp_business_account":
        return None
    try:
        value = body["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError, TypeError):
        return None

    messages = value.get("messages")
    if not messages:
        return None  # e.g. delivery/read status callbacks

    msg = messages[0]
    phone_number_id = value.get("metadata", {}).get("phone_number_id", "")
    from_number = msg.get("from", "")
    message_id = msg.get("id", "")
    mtype = msg.get("type", "unsupported")

    # The contact's display name, when WhatsApp includes it.
    contacts = value.get("contacts") or []
    profile_name = (contacts[0].get("profile", {}).get("name") if contacts else None)

    if mtype == "text":
        return IncomingMessage(from_number, phone_number_id, message_id, "text",
                               text=msg["text"]["body"], profile_name=profile_name)
    if mtype == "image":
        image = msg.get("image", {})
        return IncomingMessage(from_number, phone_number_id, message_id, "image",
                               text=image.get("caption", ""), media_id=image.get("id"),
                               profile_name=profile_name)
    if mtype == "audio":
        return IncomingMessage(from_number, phone_number_id, message_id, "audio",
                               media_id=msg.get("audio", {}).get("id"),
                               profile_name=profile_name)

    return IncomingMessage(from_number, phone_number_id, message_id, "unsupported",
                           profile_name=profile_name)
