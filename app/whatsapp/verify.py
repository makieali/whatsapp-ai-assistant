"""Webhook verification: subscription handshake + payload signature.

The original only checked the subscription verify token. Meta also signs every
webhook POST with ``X-Hub-Signature-256`` (HMAC-SHA256 of the raw body using the
app secret). Verifying it ensures requests genuinely come from Meta and not a
spoofer hitting your public endpoint.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Optional


def verify_subscription(mode: Optional[str], token: Optional[str],
                        expected_token: Optional[str]) -> bool:
    """True if the GET subscription handshake is valid."""
    return bool(mode == "subscribe" and token and token == expected_token)


def verify_signature(raw_body: bytes, signature_header: Optional[str],
                     app_secret: Optional[str]) -> bool:
    """Validate the X-Hub-Signature-256 header against the raw request body.

    If no app secret is configured, signature checking is skipped (returns True)
    so the app still runs in local/dev setups -- the README flags this.
    """
    if not app_secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    received = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, received)
