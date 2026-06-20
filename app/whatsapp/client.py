"""Outbound calls to the WhatsApp Cloud API (Graph API)."""
from __future__ import annotations

import requests

from config import Config

_TIMEOUT = 30


def _headers() -> dict:
    return {"Authorization": f"Bearer {Config.WHATSAPP_TOKEN}"}


def _graph_url(path: str) -> str:
    return f"https://graph.facebook.com/{Config.GRAPH_API_VERSION}/{path}"


def send_text(phone_number_id: str, to_number: str, message: str) -> dict:
    """Send a text message back to the user."""
    url = _graph_url(f"{phone_number_id}/messages")
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message[:4096]},  # WhatsApp text body limit
    }
    resp = requests.post(url, json=payload, headers=_headers(), timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def mark_read(phone_number_id: str, message_id: str) -> None:
    """Mark an incoming message as read (the blue ticks)."""
    url = _graph_url(f"{phone_number_id}/messages")
    payload = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}
    try:
        requests.post(url, json=payload, headers=_headers(), timeout=_TIMEOUT)
    except requests.RequestException:
        pass  # non-critical


def get_media_url(media_id: str) -> str:
    """Resolve a media id to a temporary download URL."""
    resp = requests.get(_graph_url(media_id), headers=_headers(), timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()["url"]


def download_media(media_url: str) -> tuple[bytes, str]:
    """Download media bytes; returns (content, mime_type)."""
    resp = requests.get(media_url, headers=_headers(), timeout=_TIMEOUT)
    resp.raise_for_status()
    mime = resp.headers.get("Content-Type", "application/octet-stream").split(";")[0]
    return resp.content, mime


def fetch_media(media_id: str) -> tuple[bytes, str]:
    """Convenience: media id -> (bytes, mime_type)."""
    return download_media(get_media_url(media_id))
