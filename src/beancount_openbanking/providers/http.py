"""Shared HTTP utilities for provider implementations."""

from __future__ import annotations

import logging
import time
from typing import Any, cast

import requests
import requests_cache

logger = logging.getLogger(__name__)

RATE_LIMIT_MAX_RETRIES = 3
RATE_LIMIT_BACKOFF_BASE = 1

_DEFAULT_CACHE_OPTIONS: dict[str, Any] = {
    "backend": "sqlite",
    "expire_after": 0,
    "old_data_on_error": True,
    "match_headers": False,
    "cache_control": False,
}

_HEADERS_TO_PRESERVE = {
    "content-type",
    "date",
    "content-encoding",
    "content-language",
    "last-modified",
    "location",
}


def strip_headers_hook(response, *args, **kwargs):
    """Strip response headers that override requests_cache behavior."""
    deleted = set()
    for header in list(response.headers.keys()):
        if header.lower() in _HEADERS_TO_PRESERVE:
            continue
        response.headers.pop(header, None)
        deleted.add(header)
    if deleted:
        logger.debug("Deleted headers: %s", ", ".join(deleted))
    return response


def create_cached_session(
    cache_options: dict[str, Any] | None = None,
    *,
    default_cache_name: str = "openbanking",
) -> requests.Session:
    """Return a :class:`requests.Session` with caching configured."""
    if cache_options is None:
        return requests.Session()

    defaults: dict[str, Any] = {
        **_DEFAULT_CACHE_OPTIONS,
        "cache_name": default_cache_name,
    }
    defaults.update(cache_options)
    session = cast(requests.Session, requests_cache.CachedSession(**defaults))
    session.hooks["response"].append(strip_headers_hook)
    return session


def send_with_rate_limit_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    max_retries: int = RATE_LIMIT_MAX_RETRIES,
    backoff_base: float = RATE_LIMIT_BACKOFF_BASE,
    **kwargs: Any,
) -> requests.Response:
    """Send a request with exponential back-off on HTTP 429."""
    attempt = 0
    while True:
        response = session.request(method, url, **kwargs)
        if response.status_code != 429:
            return response
        if attempt >= max_retries:
            return response
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                wait = float(retry_after)
            except (ValueError, TypeError):
                wait = backoff_base * (2**attempt)
        else:
            wait = backoff_base * (2**attempt)
        logger.warning(
            "Rate limited (429). Retrying in %.1f seconds (attempt %d/%d)",
            wait,
            attempt + 1,
            max_retries,
        )
        time.sleep(wait)
        attempt += 1
