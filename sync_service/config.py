"""Configuration management for the Nexudus → Doorflow sync service."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional


DEFAULT_POLL_INTERVAL_SECONDS = 60
DEFAULT_REQUEST_TIMEOUT = 15
DEFAULT_MAX_RETRIES = 3
DEFAULT_SYNC_INTERVAL = timedelta(minutes=5)
DEFAULT_PAGE_SIZE = 200


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Environment variable {name} must be an integer")


def _get_timedelta_seconds(name: str, default_seconds: int) -> timedelta:
    return timedelta(seconds=_get_int(name, default_seconds))


@dataclass
class Config:
    """Runtime configuration values sourced from environment variables."""

    nexudus_username: str
    nexudus_password: str
    doorflow_auth_key: str
    doorflow_system_id: str

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./nexudus_sync.db")
    poll_interval: timedelta = _get_timedelta_seconds(
        "POLL_INTERVAL_SECONDS", DEFAULT_POLL_INTERVAL_SECONDS
    )
    request_timeout_seconds: int = _get_int(
        "REQUEST_TIMEOUT_SECONDS", DEFAULT_REQUEST_TIMEOUT
    )
    max_retries: int = _get_int("MAX_HTTP_RETRIES", DEFAULT_MAX_RETRIES)
    sync_interval: timedelta = _get_timedelta_seconds(
        "DOORFLOW_SYNC_INTERVAL_SECONDS", int(DEFAULT_SYNC_INTERVAL.total_seconds())
    )
    page_size: int = _get_int("NEXUDUS_PAGE_SIZE", DEFAULT_PAGE_SIZE)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    team_mapping_path: Optional[str] = os.getenv("TEAM_MAPPING_PATH")


    @classmethod
    def from_env(cls) -> "Config":
        required = {
            "NEXUDUS_USERNAME": os.getenv("NEXUDUS_USERNAME"),
            "NEXUDUS_PASSWORD": os.getenv("NEXUDUS_PASSWORD"),
            "DOORFLOW_AUTH_KEY": os.getenv("DOORFLOW_AUTH_KEY"),
            "DOORFLOW_SYSTEM_ID": os.getenv("DOORFLOW_SYSTEM_ID"),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            missing_str = ", ".join(missing)
            raise EnvironmentError(f"Missing required environment variables: {missing_str}")

        return cls(
            nexudus_username=required["NEXUDUS_USERNAME"],
            nexudus_password=required["NEXUDUS_PASSWORD"],
            doorflow_auth_key=required["DOORFLOW_AUTH_KEY"],
            doorflow_system_id=required["DOORFLOW_SYSTEM_ID"],
        )
