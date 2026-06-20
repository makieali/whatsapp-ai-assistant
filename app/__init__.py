"""Flask application factory."""
from __future__ import annotations

import logging

from flask import Flask

from config import Config
from app.memory import build_memory


def create_app(config_class=Config, memory=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.secret_key = config_class.SECRET_KEY
    app.memory = memory or build_memory(config_class)

    logging.basicConfig(
        level=logging.DEBUG if config_class.DEBUG else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from app.routes import bp

    app.register_blueprint(bp)
    return app
