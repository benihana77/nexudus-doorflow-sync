"""Data access and diffing utilities."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Iterable, List, Tuple

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from sync_service.db.models import ChangeLog, DoorflowGroup, Member, Membership, SyncState, Team

logger = logging.getLogger(__name__)


class SnapshotRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_members(self, payloads: Iterable[Dict]) -> List[Member]:
        members = []
        for payload in payloads:
            member = Member.from_payload(payload)
            existing = self.session.get(Member, member.id)
            if existing:
                if existing.payload_hash == member.payload_hash:
                    members.append(existing)
                    continue
                logger.debug("Updating member %s", member.id)
                for attr in [
                    "user_id",
                    "email",
                    "full_name",
                    "active",
                    "access_pin",
                    "key_fob_number",
                    "credentials_number",
                    "raw_payload",
                    "payload_hash",
                ]:
                    setattr(existing, attr, getattr(member, attr))
                members.append(existing)
            else:
                logger.debug("Creating member %s", member.id)
                self.session.add(member)
                members.append(member)
        return members

    def upsert_teams(self, payloads: Iterable[Dict]) -> List[Team]:
        teams: List[Team] = []
        for payload in payloads:
            team = Team.from_payload(payload)
            existing = self.session.get(Team, team.id)
            if existing:
                if existing.payload_hash == team.payload_hash:
                    teams.append(existing)
                    continue
                existing.name = team.name
                existing.raw_payload = team.raw_payload
                existing.payload_hash = team.payload_hash
                teams.append(existing)
            else:
                self.session.add(team)
                teams.append(team)
        return teams

    def replace_memberships(self, member_id: int, payloads: Iterable[Dict]):
        self.session.execute(
            delete(Membership).where(Membership.member_id == member_id)
        )
        for payload in payloads:
            membership = Membership.from_payload(member_id, payload)
            self.session.add(membership)

    def record_change(self, member_id: int, change_type: str, description: str, payload=None, correlation_id: str | None = None, doorflow_status: str | None = None):
        log_entry = ChangeLog(
            member_id=member_id,
            change_type=change_type,
            description=description,
            payload=payload,
            correlation_id=correlation_id,
            doorflow_status=doorflow_status,
        )
        self.session.add(log_entry)
        return log_entry

    def get_sync_state(self) -> SyncState:
        state = self.session.execute(select(SyncState)).scalar_one_or_none()
        if not state:
            state = SyncState()
            self.session.add(state)
        return state

    def update_last_poll(self):
        state = self.get_sync_state()
        state.last_nexudus_poll = datetime.utcnow()

    def update_last_reader_sync(self):
        state = self.get_sync_state()
        state.last_reader_sync = datetime.utcnow()

    def load_team_mapping(self) -> Dict[str, str]:
        mapping = {}
        for row in self.session.execute(select(DoorflowGroup)).scalars():
            mapping[row.nexudus_team_id] = row.doorflow_group_id
        return mapping

    def seed_team_mapping(self, mapping_rows: Iterable[Tuple[str, str, str | None]]):
        for nexudus_id, doorflow_id, doorflow_name in mapping_rows:
            existing = (
                self.session.execute(
                    select(DoorflowGroup).where(DoorflowGroup.nexudus_team_id == nexudus_id)
                ).scalar_one_or_none()
            )
            if existing:
                existing.doorflow_group_id = doorflow_id
                existing.doorflow_group_name = doorflow_name
            else:
                self.session.add(
                    DoorflowGroup(
                        nexudus_team_id=nexudus_id,
                        doorflow_group_id=doorflow_id,
                        doorflow_group_name=doorflow_name,
                    )
                )
