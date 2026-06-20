"""Test fixtures: webhook payload builders and fakes for AI + WhatsApp I/O."""
import pytest

from config import Config


# ---- webhook payload builders ----

def text_payload(body="Hello", from_number="15551230000", phone_id="PHONE123"):
    return _envelope(phone_id, {
        "from": from_number, "id": "wamid.TEXT1", "type": "text",
        "text": {"body": body},
    })


def image_payload(caption="", media_id="MEDIA_IMG", from_number="15551230000", phone_id="PHONE123"):
    return _envelope(phone_id, {
        "from": from_number, "id": "wamid.IMG1", "type": "image",
        "image": {"id": media_id, "caption": caption, "mime_type": "image/jpeg"},
    })


def audio_payload(media_id="MEDIA_AUD", from_number="15551230000", phone_id="PHONE123"):
    return _envelope(phone_id, {
        "from": from_number, "id": "wamid.AUD1", "type": "audio",
        "audio": {"id": media_id, "mime_type": "audio/ogg"},
    })


def status_payload(phone_id="PHONE123"):
    """A delivery-status callback (no 'messages' key)."""
    return _envelope(phone_id, None, statuses=[{"status": "delivered"}])


def _envelope(phone_id, message, statuses=None):
    value = {"messaging_product": "whatsapp", "metadata": {"phone_number_id": phone_id}}
    if message is not None:
        value["messages"] = [message]
    if statuses is not None:
        value["statuses"] = statuses
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA", "changes": [{"value": value, "field": "messages"}]}],
    }


# ---- fakes ----

@pytest.fixture
def fake_ai(monkeypatch):
    """Stub the AI layer so no model is called."""
    import app.ai as ai
    import app.handler as handler_mod
    calls = {"text": [], "image": [], "audio": []}

    def reply_text(history):
        calls["text"].append(history)
        return "AI reply"

    def reply_about_image(history, image_bytes, mime, caption):
        calls["image"].append((len(image_bytes), mime, caption))
        return "I see a cat."

    def transcribe_audio(audio_bytes, filename="voice.ogg"):
        calls["audio"].append(len(audio_bytes))
        return "transcribed words"

    for mod in (ai, handler_mod.ai):
        monkeypatch.setattr(mod, "reply_text", reply_text)
        monkeypatch.setattr(mod, "reply_about_image", reply_about_image)
        monkeypatch.setattr(mod, "transcribe_audio", transcribe_audio)
    return calls


@pytest.fixture
def fake_wa(monkeypatch):
    """Stub outbound WhatsApp calls; record what would have been sent."""
    from app.whatsapp import client as wa
    import app.handler as handler_mod
    sent = []

    def send_text(phone_number_id, to_number, message):
        sent.append({"to": to_number, "message": message})
        return {"messages": [{"id": "wamid.SENT"}]}

    def mark_read(phone_number_id, message_id):
        pass

    def fetch_media(media_id):
        return (b"\x89PNG fake-bytes", "image/jpeg")

    for target in (wa, handler_mod.wa):
        monkeypatch.setattr(target, "send_text", send_text)
        monkeypatch.setattr(target, "mark_read", mark_read)
        monkeypatch.setattr(target, "fetch_media", fetch_media)
    return sent


@pytest.fixture
def app(monkeypatch):
    from app import create_app
    monkeypatch.setattr(Config, "WHATSAPP_VERIFY_TOKEN", "verify-me")
    monkeypatch.setattr(Config, "WHATSAPP_APP_SECRET", None)  # skip sig check by default
    monkeypatch.setattr(Config, "WHATSAPP_TOKEN", "wa-token")
    monkeypatch.setattr(Config, "WHATSAPP_PHONE_NUMBER_ID", "PHONE123")
    flask_app = create_app()
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture
def http(app):
    return app.test_client()
