"""Database models for the Nexudus → Doorflow sync service."""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


def _hash_payload(payload: Dict[str, Any]) -> str:
    serialized = repr(sorted(payload.items())).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, autoincrement=False)
    user_id = Column(Integer, nullable=True)
    email = Column(String, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    access_pin = Column(String, nullable=True)
    key_fob_number = Column(String, nullable=True)
    credentials_number = Column(String, nullable=True)
    raw_payload = Column(JSON, nullable=False)
    payload_hash = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    memberships = relationship("Membership", back_populates="member", cascade="all, delete-orphan")

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "Member":
        return cls(
            id=payload.get("Id"),
            user_id=payload.get("UserId"),
            email=payload.get("Email", ""),
            full_name=payload.get("FullName", ""),
            active=payload.get("Cancelled", False) is False,
            access_pin=payload.get("AccessPincode"),
            key_fob_number=payload.get("KeyFobNumber"),
            credentials_number=payload.get("AccessCardId"),
            raw_payload=payload,
            payload_hash=_hash_payload(payload),
        )


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(String, nullable=False)
    raw_payload = Column(JSON, nullable=False)
    payload_hash = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    memberships = relationship("Membership", back_populates="team", cascade="all, delete-orphan")

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "Team":
        return cls(
            id=payload.get("Id"),
            name=payload.get("Name", ""),
            raw_payload=payload,
            payload_hash=_hash_payload(payload),
        )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("member_id", "team_id", name="uq_member_team"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    member_id = Column(Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    raw_payload = Column(JSON, nullable=False)
    payload_hash = Column(String, nullable=False)

    member = relationship("Member", back_populates="memberships")
    team = relationship("Team", back_populates="memberships")

    @classmethod
    def from_payload(cls, member_id: int, payload: Dict[str, Any]) -> "Membership":
        team_id = payload.get("TeamId") or payload.get("Id")
        return cls(
            member_id=member_id,
            team_id=team_id,
            raw_payload=payload,
            payload_hash=_hash_payload(payload),
        )


class DoorflowGroup(Base):
    __tablename__ = "doorflow_groups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nexudus_team_id = Column(String, nullable=False, unique=True)
    doorflow_group_id = Column(String, nullable=False)
    doorflow_group_name = Column(String, nullable=True)


class ChangeLog(Base):
    __tablename__ = "change_log"

    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, nullable=False)
    change_type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    doorflow_status = Column(String, nullable=True)
    correlation_id = Column(String, nullable=True)
    payload = Column(JSON, nullable=True)


class SyncState(Base):
    __tablename__ = "sync_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    last_nexudus_poll = Column(DateTime, nullable=True)
    last_reader_sync = Column(DateTime, nullable=True)


__all__ = [
    "Base",
    "Member",
    "Team",
    "Membership",
    "DoorflowGroup",
    "ChangeLog",
    "SyncState",
]
