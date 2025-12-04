"""HTTP client helpers with retries and timeouts."""
from __future__ import annotations

import logging
from typing import Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


def build_session(timeout: int, max_retries: int) -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=max_retries,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.request = _wrap_request(session.request, timeout)
    return session


def _wrap_request(request_func, timeout: int):
    def wrapped(method: str, url: str, **kwargs):
        kwargs.setdefault("timeout", timeout)
        return request_func(method, url, **kwargs)

    return wrapped
