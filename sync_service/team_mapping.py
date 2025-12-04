"""Utilities for loading Nexudus → Doorflow group mappings."""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from sync_service.repository import SnapshotRepository

logger = logging.getLogger(__name__)


def sync_team_mapping(
    session: Session,
    mapping_path: Optional[str],
    nexudus_teams: Sequence[dict],
    doorflow_groups: Sequence[dict],
) -> Dict[str, str]:
    """
    Build Nexudus→Doorflow mappings by preferring a CSV override and
    falling back to name-based pairing of teams and groups.
    """

    repo = SnapshotRepository(session)

    if mapping_path:
        _load_team_mapping_file(repo, mapping_path)

    mappings = _map_by_name(nexudus_teams, doorflow_groups)
    if mappings:
        repo.seed_team_mapping(mappings)

    return repo.load_team_mapping()


def _load_team_mapping_file(repo: SnapshotRepository, mapping_path: str) -> None:
    path = Path(mapping_path)
    if not path.exists():
        logger.warning("Team mapping file %s not found; proceeding without mappings", mapping_path)
        return
    rows = []
    with path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append((row.get("nexudus_id"), row.get("doorflow_id"), row.get("doorflow_name")))
    repo.seed_team_mapping(rows)


def _map_by_name(
    nexudus_teams: Sequence[dict], doorflow_groups: Sequence[dict]
) -> Iterable[tuple[str, str, Optional[str]]]:
    if not nexudus_teams or not doorflow_groups:
        return []

    def _name(payload: dict) -> Optional[str]:
        name = payload.get("Name") or payload.get("name")
        return name.strip() if isinstance(name, str) else None

    doorflow_by_name = {}
    for group in doorflow_groups:
        name = _name(group)
        if not name:
            continue
        doorflow_by_name[name.lower()] = (str(group.get("id") or group.get("Id")), name)

    mappings = []
    for team in nexudus_teams:
        name = _name(team)
        if not name:
            continue
        match = doorflow_by_name.get(name.lower())
        if not match or not match[0]:
            logger.debug("No Doorflow group match for Nexudus team '%s'", name)
            continue
        nexudus_id = str(team.get("Id") or team.get("TeamId"))
        if not nexudus_id:
            continue
        doorflow_id, doorflow_name = match
        mappings.append((nexudus_id, doorflow_id, doorflow_name))

    if not mappings:
        logger.warning("No Nexudus teams matched Doorflow groups by name")

    return mappings
