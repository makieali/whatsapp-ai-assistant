"""Tests for the outbound WhatsApp client using mocked HTTP."""
import responses

from config import Config
from app.whatsapp import client as wa


@responses.activate
def test_send_text_posts_correct_payload(monkeypatch):
    monkeypatch.setattr(Config, "WHATSAPP_TOKEN", "tok")
    monkeypatch.setattr(Config, "GRAPH_API_VERSION", "v21.0")
    url = "https://graph.facebook.com/v21.0/PHONE/messages"
    responses.add(responses.POST, url, json={"messages": [{"id": "wamid.X"}]}, status=200)

    result = wa.send_text("PHONE", "15551230000", "hello world")

    assert result["messages"][0]["id"] == "wamid.X"
    req = responses.calls[0].request
    assert req.headers["Authorization"] == "Bearer tok"
    import json
    sent = json.loads(req.body)
    assert sent["to"] == "15551230000"
    assert sent["text"]["body"] == "hello world"
    assert sent["messaging_product"] == "whatsapp"


@responses.activate
def test_send_text_truncates_long_messages(monkeypatch):
    monkeypatch.setattr(Config, "WHATSAPP_TOKEN", "tok")
    url = f"https://graph.facebook.com/{Config.GRAPH_API_VERSION}/P/messages"
    responses.add(responses.POST, url, json={"messages": [{}]}, status=200)
    wa.send_text("P", "1555", "x" * 5000)
    import json
    body = json.loads(responses.calls[0].request.body)
    assert len(body["text"]["body"]) == 4096


@responses.activate
def test_fetch_media_resolves_and_downloads(monkeypatch):
    monkeypatch.setattr(Config, "WHATSAPP_TOKEN", "tok")
    base = f"https://graph.facebook.com/{Config.GRAPH_API_VERSION}"
    responses.add(responses.GET, f"{base}/MID", json={"url": "https://cdn.example/file"}, status=200)
    responses.add(responses.GET, "https://cdn.example/file", body=b"BINARY",
                  content_type="image/jpeg", status=200)

    data, mime = wa.fetch_media("MID")
    assert data == b"BINARY"
    assert mime == "image/jpeg"
