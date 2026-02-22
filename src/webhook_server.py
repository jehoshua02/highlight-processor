"""Lightweight Flask server to handle Instagram webhook verification and events."""

import os
import logging
from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

VERIFY_TOKEN = os.environ.get("IG_WEBHOOK_VERIFY_TOKEN", "")


@app.route("/webhook/instagram", methods=["GET"])
def verify():
    """Respond to Meta's webhook verification challenge."""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        app.logger.info("Webhook verified successfully")
        return challenge, 200
    else:
        app.logger.warning("Webhook verification failed")
        return "Forbidden", 403


@app.route("/webhook/instagram", methods=["POST"])
def webhook():
    """Receive Instagram webhook event notifications."""
    payload = request.get_json(silent=True)
    app.logger.info("Webhook event received: %s", payload)
    # TODO: process incoming webhook events
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
