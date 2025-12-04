"""Structured logging and metrics hooks."""
from __future__ import annotations

import logging
from logging.config import dictConfig


def setup_logging(level: str = "INFO"):
    dictConfig(
        {
            "version": 1,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "root": {
                "handlers": ["console"],
                "level": level,
            },
        }
    )


def get_health_state(db_check: bool = False):
    return {"ok": True, "db": db_check}
