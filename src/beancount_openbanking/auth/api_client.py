"""Shared HTTP client for the Enable Banking API.

Both ``SessionManager`` (auth/) and ``EnableBankingProvider`` (providers/)
call the same ``https://api.enablebanking.com`` host with JWT-signed
headers and rate-limit-retry semantics. This module owns the shared
request builder so the two call sites cannot drift.
"""

from __future__ import annotations

from typing import Any, Callable

import requests

from ..providers.http import send_with_rate_limit_retry

ENABLE_BANKING_BASE_URL = "https://api.enablebanking.com"


class EnableBankingApiClient:
    """Thin wrapper that prepends the Enable Banking base URL, signs each
    request, retries on 429, and raises on non-2xx responses."""

    def __init__(
        self,
        http: requests.Session,
        build_headers: Callable[[], dict[str, str]],
        *,
        base_url: str = ENABLE_BANKING_BASE_URL,
        timeout: int = 30,
    ) -> None:
        self.http = http
        self._build_headers = build_headers
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> requests.Response:
        """Send ``method path`` to the API and return the response.

        ``path`` is joined onto ``base_url``. Per-call ``headers`` are
        merged on top of the signed headers from ``build_headers``.
        """
        headers = kwargs.pop("headers", {})
        response = send_with_rate_limit_retry(
            self.http,
            method,
            f"{self.base_url}{path}",
            headers={**self._build_headers(), **headers},
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response
