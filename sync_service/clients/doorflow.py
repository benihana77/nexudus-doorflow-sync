"""Doorflow API client with idempotent operations and sync scheduling."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from requests.auth import HTTPBasicAuth

from sync_service.config import Config
from sync_service.clients.http import build_session

logger = logging.getLogger(__name__)


class DoorflowClient:
    def __init__(self, config: Config):
        self.config = config
        self.session = build_session(
            timeout=config.request_timeout_seconds, max_retries=config.max_retries
        )
        self.session.auth = HTTPBasicAuth(config.doorflow_auth_key, "x")

    def upsert_user(self, member_payload: Dict, groups: List[str]) -> Optional[str]:
        user_payload = {
            "email": member_payload.get("Email"),
            "full_name": member_payload.get("FullName"),
            "pin": member_payload.get("AccessPincode"),
            "key_fob_number": member_payload.get("KeyFobNumber"),
            "credentials_number": member_payload.get("AccessCardId"),
            "system_id": self.config.doorflow_system_id,
            "groups": groups,
            "enabled": not member_payload.get("Cancelled", False),
        }
        response = self.session.put(
            "https://admin.doorflow.com/api/2/people",
            json=user_payload,
        )
        if not response.ok:
            logger.error("Doorflow upsert failed: %s %s", response.status_code, response.text)
            return None
        return response.headers.get("X-Correlation-ID") or response.headers.get("x-correlation-id")

    def fetch_groups(self) -> List[Dict]:
        """Return all Doorflow groups with ids and names for mapping purposes."""
        response = self.session.get("https://admin.doorflow.com/api/2/groups")
        if not response.ok:
            logger.error(
                "Doorflow group fetch failed: %s %s", response.status_code, response.text
            )
            return []
        try:
            data = response.json()
        except Exception:
            logger.exception("Failed to parse Doorflow group response")
            return []
        return data if isinstance(data, list) else []

    def sync_readers(self) -> bool:
        response = self.session.post("https://admin.doorflow.com/api/2/sync")
        if not response.ok:
            logger.error("Doorflow reader sync failed: %s %s", response.status_code, response.text)
            return False
        return True

    def should_sync(self, last_sync: Optional[datetime]) -> bool:
        if not last_sync:
            return True
        return datetime.utcnow() - last_sync >= self.config.sync_interval

    def enforce_sync_interval(self, last_sync: Optional[datetime]) -> Optional[timedelta]:
        if not last_sync:
            return None
        delta = datetime.utcnow() - last_sync
        remaining = self.config.sync_interval - delta
        return remaining if remaining.total_seconds() > 0 else None
