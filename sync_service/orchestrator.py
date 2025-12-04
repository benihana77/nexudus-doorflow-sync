"""Polling loop orchestrator."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Dict, List

from sqlalchemy import select

from sync_service.change_detection import ChangeDetector
from sync_service.clients.doorflow import DoorflowClient
from sync_service.clients.nexudus import NexudusClient
from sync_service.config import Config
from sync_service.db.models import Member, Membership, Team
from sync_service.db.session import session_scope
from sync_service.repository import SnapshotRepository
from sync_service.team_mapping import sync_team_mapping

logger = logging.getLogger(__name__)


class SyncOrchestrator:
    def __init__(self, config: Config, Session):
        self.config = config
        self.Session = Session
        self.nexudus = NexudusClient(config)
        self.doorflow = DoorflowClient(config)

    def run_forever(self):
        logger.info("Starting Nexudus → Doorflow sync loop with %s interval", self.config.poll_interval)
        while True:
            try:
                self.run_once()
            except Exception:
                logger.exception("Unexpected error in sync cycle")
            time.sleep(self.config.poll_interval.total_seconds())

    def run_once(self):
        with session_scope(self.Session) as session:
            repo = SnapshotRepository(session)
            state = repo.get_sync_state()
            last_poll = state.last_nexudus_poll

            existing_members = {m.id: m for m in session.execute(select(Member)).scalars()}
            existing_memberships: Dict[int, List[Membership]] = {}
            for membership in session.execute(select(Membership)).scalars():
                existing_memberships.setdefault(membership.member_id, []).append(membership)

            coworkers = self.nexudus.fetch_coworkers(last_poll)
            teams = self.nexudus.fetch_teams()
            doorflow_groups = self.doorflow.fetch_groups()
            memberships_payloads = self.nexudus.fetch_memberships([c.get("Id") for c in coworkers])

            members = repo.upsert_members(coworkers)
            team_models = repo.upsert_teams(teams)

            membership_models: Dict[int, List[Membership]] = {}
            for member in members:
                payloads = memberships_payloads.get(member.id, [])
                repo.replace_memberships(member.id, payloads)
                membership_models[member.id] = [Membership.from_payload(member.id, p) for p in payloads]

            detector = ChangeDetector(existing_members, existing_memberships)
            changes = detector.detect(members, membership_models)

            mapping = sync_team_mapping(
                session=session,
                mapping_path=self.config.team_mapping_path,
                nexudus_teams=teams,
                doorflow_groups=doorflow_groups,
            )
            changes_applied = False

            for change in changes:
                group_ids = self._resolve_groups(change, mapping)
                correlation_id = self.doorflow.upsert_user(change.member.raw_payload, group_ids)
                status = "applied" if correlation_id else "failed"
                repo.record_change(
                    member_id=change.member.id,
                    change_type=change.change_type,
                    description=change.reason,
                    payload={"groups": group_ids},
                    correlation_id=correlation_id,
                    doorflow_status=status,
                )
                changes_applied = changes_applied or bool(correlation_id)

            if changes_applied and self.doorflow.should_sync(state.last_reader_sync):
                if self.doorflow.sync_readers():
                    repo.update_last_reader_sync()

            repo.update_last_poll()
            logger.info(
                "Sync cycle completed: %s coworkers, %s teams, %s changes", len(coworkers), len(teams), len(changes)
            )

    def _resolve_groups(self, change, mapping: Dict[str, str]) -> List[str]:
        group_ids: List[str] = []
        for membership in change.memberships:
            mapped = mapping.get(str(membership.team_id))
            if mapped:
                group_ids.append(mapped)
        if not group_ids:
            logger.debug("No mapping found for member %s; defaulting to base access", change.member.id)
        return group_ids
