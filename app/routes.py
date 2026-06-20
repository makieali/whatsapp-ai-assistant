"""HTTP routes: landing page, health check, and the WhatsApp webhook."""
from __future__ import annotations

import logging

from flask import Blueprint, current_app, jsonify, render_template, request

from config import Config
from app import handler
from app.whatsapp import parse_webhook, verify_signature, verify_subscription

logger = logging.getLogger(__name__)
bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    return render_template("index.html", model=Config.chat_model())


@bp.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@bp.get("/webhook")
def webhook_verify():
    """Meta subscription handshake."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge", "")
    if verify_subscription(mode, token, Config.WHATSAPP_VERIFY_TOKEN):
        return challenge, 200
    return jsonify({"error": "verification failed"}), 403


@bp.post("/webhook")
def webhook_receive():
    """Receive and process an inbound WhatsApp event."""
    if not verify_signature(
        request.get_data(), request.headers.get("X-Hub-Signature-256"),
        Config.WHATSAPP_APP_SECRET,
    ):
        return jsonify({"error": "invalid signature"}), 403

    body = request.get_json(silent=True) or {}
    message = parse_webhook(body)

    # Always 200 quickly for non-message events so Meta doesn't retry.
    if message is None:
        return jsonify({"status": "ignored"}), 200
    if message.type == "unsupported" and not message.from_number:
        return jsonify({"status": "ignored"}), 200

    try:
        handler.handle_incoming(message, current_app.memory)
    except Exception:  # noqa: BLE001 - never 500 the webhook; Meta would retry
        logger.exception("Failed handling message")
    return jsonify({"status": "ok"}), 200
