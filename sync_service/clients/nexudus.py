"""Client for Nexudus APIs."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import requests

from sync_service.config import Config
from sync_service.clients.http import build_session

logger = logging.getLogger(__name__)


class NexudusClient:
    def __init__(self, config: Config):
        self.config = config
        self.session = build_session(
            timeout=config.request_timeout_seconds, max_retries=config.max_retries
        )
        self.session.auth = (config.nexudus_username, config.nexudus_password)

    def _get_paginated(self, url: str, params: Optional[Dict] = None) -> Iterable[Dict]:
        params = params or {}
        params.setdefault("page", 1)
        params.setdefault("size", self.config.page_size)

        while True:
            response = self.session.get(url, params=params)
            if not response.ok:
                logger.error("Nexudus request failed: %s %s", response.status_code, response.text)
                break
            payload = response.json()
            for record in payload.get("Records", []):
                yield record
            if params["page"] >= payload.get("PageCount", params["page"]):
                break
            params["page"] += 1

    def fetch_coworkers(self, updated_since: Optional[datetime]) -> List[Dict]:
        params: Dict[str, str] = {}
        if updated_since:
            params["Coworker_UpdatedOn_Gt"] = updated_since.isoformat()
        url = "https://spaces.nexudus.com/api/spaces/coworkers"
        return list(self._get_paginated(url, params))

    def fetch_teams(self) -> List[Dict]:
        url = "https://spaces.nexudus.com/api/spaces/teams"
        return list(self._get_paginated(url))

    def fetch_memberships(self, coworker_ids: List[int]) -> Dict[int, List[Dict]]:
        memberships: Dict[int, List[Dict]] = {}
        for coworker_id in coworker_ids:
            url = "https://spaces.nexudus.com/api/spaces/teamcoworkers"
            params = {"TeamCoworker_Coworker_Id": coworker_id, "size": self.config.page_size}
            memberships[coworker_id] = list(self._get_paginated(url, params))
        return memberships
