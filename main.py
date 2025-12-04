"""Entry point for the redesigned Nexudus → Doorflow sync service."""
from __future__ import annotations

import logging
import os

from sync_service.config import Config
from sync_service.db.session import create_session_factory
from sync_service.orchestrator import SyncOrchestrator
from sync_service.telemetry import setup_logging
from sync_service.team_mapping import load_team_mapping


def main():
    config = Config.from_env()
    setup_logging(config.log_level)
    Session = create_session_factory(config.database_url)

    # Seed team mapping table if provided
    with Session() as session:
        load_team_mapping(session, config.team_mapping_path)
        session.commit()

    orchestrator = SyncOrchestrator(config, Session)
    orchestrator.run_forever()


if __name__ == "__main__":
    main()
