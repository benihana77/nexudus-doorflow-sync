"""Minimal web UI to display sync status and recent changes."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from flask import Flask, jsonify, render_template
from sqlalchemy import func, select

from sync_service.db.models import ChangeLog, Member, SyncState, Team
from sync_service.db.session import create_session_factory
from sync_service.telemetry import setup_logging

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nexudus_sync.db")
LISTEN_HOST = os.getenv("STATUS_HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("STATUS_PORT", "8000"))

setup_logging(LOG_LEVEL)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates")
Session = create_session_factory(DATABASE_URL)


def _format_timestamp(value: Optional[datetime]) -> str:
    if not value:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


@app.route("/status.json")
def status_json():
    data = _gather_status()
    return jsonify(data)


@app.route("/")
def dashboard():
    data = _gather_status()
    return render_template("status.html", **data)


def _gather_status() -> Dict:
    with Session() as session:
        state: Optional[SyncState] = session.execute(select(SyncState)).scalar_one_or_none()
        last_poll = state.last_nexudus_poll if state else None
        last_reader_sync = state.last_reader_sync if state else None

        total_members = session.execute(select(func.count()).select_from(Member)).scalar_one()
        active_members = (
            session.execute(select(func.count()).select_from(Member).where(Member.active)).scalar_one()
        )
        team_count = session.execute(select(func.count()).select_from(Team)).scalar_one()

        recent_changes: List[ChangeLog] = (
            session.execute(select(ChangeLog).order_by(ChangeLog.created_at.desc()).limit(50))
            .scalars()
            .all()
        )

    return {
        "last_poll": _format_timestamp(last_poll),
        "last_reader_sync": _format_timestamp(last_reader_sync),
        "total_members": total_members,
        "active_members": active_members,
        "team_count": team_count,
        "recent_changes": [
            {
                "id": row.id,
                "member_id": row.member_id,
                "change_type": row.change_type,
                "description": row.description,
                "doorflow_status": row.doorflow_status,
                "created_at": _format_timestamp(row.created_at),
            }
            for row in recent_changes
        ],
    }


if __name__ == "__main__":
    logger.info("Starting status dashboard on %s:%s", LISTEN_HOST, LISTEN_PORT)
    app.run(host=LISTEN_HOST, port=LISTEN_PORT)
