"""Chat and vision replies.

``reply_text`` answers a text message using conversation history.
``reply_about_image`` answers about an image the user sent (the "vision" the
project name always promised but never had). Both return plain strings ready to
send back over WhatsApp.
"""
from __future__ import annotations

import base64

from .client import create_chat


def reply_text(history: list[dict]) -> str:
    """Generate an assistant reply given the full message history."""
    response = create_chat(history)
    return (response.choices[0].message.content or "").strip()


def reply_about_image(
    history: list[dict], image_bytes: bytes, mime_type: str, caption: str = ""
) -> str:
    """Answer about an image, using prior history for context."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    prompt = caption.strip() or "Describe this image and anything notable in it."
    vision_turn = {
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
        ],
    }
    response = create_chat(history + [vision_turn])
    return (response.choices[0].message.content or "").strip()
