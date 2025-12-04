"""Lightweight health/readiness endpoints using Flask."""
from __future__ import annotations

from flask import Flask, jsonify
from sqlalchemy import text

from sync_service.db.session import create_session_factory
from sync_service.telemetry import setup_logging


def create_app(database_url: str) -> Flask:
    setup_logging()
    Session = create_session_factory(database_url)
    app = Flask(__name__)

    @app.route("/healthz")
    def health():
        return jsonify({"ok": True})

    @app.route("/readyz")
    def ready():
        try:
            with Session() as session:
                session.execute(text("select 1"))
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 503
        return jsonify({"ok": True})

    return app
