"""Tests for subscription handshake and HMAC signature verification."""
import hashlib
import hmac

from app.whatsapp import verify_signature, verify_subscription


def test_subscription_valid():
    assert verify_subscription("subscribe", "tok", "tok") is True


def test_subscription_wrong_token():
    assert verify_subscription("subscribe", "bad", "tok") is False


def test_subscription_wrong_mode():
    assert verify_subscription("unsubscribe", "tok", "tok") is False


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_signature_valid():
    body = b'{"hello":"world"}'
    assert verify_signature(body, _sign(body, "s3cret"), "s3cret") is True


def test_signature_tampered_body():
    body = b'{"hello":"world"}'
    sig = _sign(body, "s3cret")
    assert verify_signature(b'{"hello":"evil"}', sig, "s3cret") is False


def test_signature_wrong_secret():
    body = b"data"
    assert verify_signature(body, _sign(body, "right"), "wrong") is False


def test_signature_missing_header():
    assert verify_signature(b"data", None, "secret") is False


def test_signature_skipped_without_secret():
    # No app secret configured -> verification is skipped (dev-friendly).
    assert verify_signature(b"data", None, None) is True
