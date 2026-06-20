"""Tests for webhook payload parsing."""
from app.whatsapp import parse_webhook
from tests.conftest import text_payload, image_payload, audio_payload, status_payload


def test_parse_text():
    m = parse_webhook(text_payload("hi there"))
    assert m.type == "text"
    assert m.text == "hi there"
    assert m.from_number == "15551230000"
    assert m.phone_number_id == "PHONE123"


def test_parse_image_with_caption():
    m = parse_webhook(image_payload(caption="what is this?", media_id="IMG9"))
    assert m.type == "image"
    assert m.media_id == "IMG9"
    assert m.text == "what is this?"


def test_parse_audio():
    m = parse_webhook(audio_payload(media_id="AUD9"))
    assert m.type == "audio"
    assert m.media_id == "AUD9"


def test_status_callback_is_none():
    assert parse_webhook(status_payload()) is None


def test_garbage_payloads_are_none():
    assert parse_webhook({}) is None
    assert parse_webhook({"object": "other"}) is None
    assert parse_webhook({"object": "whatsapp_business_account", "entry": []}) is None
    assert parse_webhook(None) is None


def test_unsupported_type():
    payload = text_payload()
    payload["entry"][0]["changes"][0]["value"]["messages"][0] = {
        "from": "1555", "id": "x", "type": "location", "location": {}
    }
    m = parse_webhook(payload)
    assert m.type == "unsupported"
