"""Integration tests for the Flask webhook routes."""
import hashlib
import hmac
import json

from config import Config
from tests.conftest import text_payload, status_payload


def test_index_and_health(http):
    assert http.get("/").status_code == 200
    assert http.get("/healthz").get_json()["status"] == "ok"


def test_webhook_verification_success(http):
    res = http.get("/webhook", query_string={
        "hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "CHALLENGE42",
    })
    assert res.status_code == 200
    assert res.data == b"CHALLENGE42"


def test_webhook_verification_failure(http):
    res = http.get("/webhook", query_string={
        "hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "x",
    })
    assert res.status_code == 403


def test_webhook_text_message_end_to_end(http, fake_ai, fake_wa):
    res = http.post("/webhook", json=text_payload("hello bot"))
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"
    assert fake_wa[0]["message"] == "AI reply"


def test_webhook_status_callback_ignored(http, fake_ai, fake_wa):
    res = http.post("/webhook", json=status_payload())
    assert res.status_code == 200
    assert res.get_json()["status"] == "ignored"
    assert fake_wa == []  # nothing sent


def test_webhook_rejects_bad_signature(http, fake_ai, fake_wa, monkeypatch):
    monkeypatch.setattr(Config, "WHATSAPP_APP_SECRET", "s3cret")
    res = http.post("/webhook", json=text_payload("hi"),
                    headers={"X-Hub-Signature-256": "sha256=deadbeef"})
    assert res.status_code == 403
    assert fake_wa == []


def test_webhook_accepts_valid_signature(http, fake_ai, fake_wa, monkeypatch):
    monkeypatch.setattr(Config, "WHATSAPP_APP_SECRET", "s3cret")
    raw = json.dumps(text_payload("hi")).encode()
    sig = "sha256=" + hmac.new(b"s3cret", raw, hashlib.sha256).hexdigest()
    res = http.post("/webhook", data=raw, content_type="application/json",
                    headers={"X-Hub-Signature-256": sig})
    assert res.status_code == 200
    assert fake_wa[0]["message"] == "AI reply"


def test_webhook_never_500s_on_handler_error(http, fake_wa, monkeypatch):
    import app.handler as h
    monkeypatch.setattr(h, "handle_incoming",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("kaboom")))
    res = http.post("/webhook", json=text_payload("hi"))
    assert res.status_code == 200  # Meta must not be told to retry
