"""Provider-facing domain models and shared HTTP utilities."""

from __future__ import annotations

import logging
import time
from datetime import date
from enum import Enum
from typing import Any, Protocol

import requests
import requests_cache
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

__all__ = [
    "Account",
    "Balance",
    "BookingStatus",
    "Provider",
    "Transaction",
    "TransactionDirection",
    "create_cached_session",
    "send_with_rate_limit_retry",
    "strip_headers_hook",
]

# ---------------------------------------------------------------------------
# Shared HTTP defaults
# ---------------------------------------------------------------------------
RATE_LIMIT_MAX_RETRIES = 3
RATE_LIMIT_BACKOFF_BASE = 1  # seconds

_DEFAULT_CACHE_OPTIONS: dict[str, Any] = {
    "backend": "sqlite",
    "expire_after": 0,
    "old_data_on_error": True,
    "match_headers": False,
    "cache_control": False,
}


# ---------------------------------------------------------------------------
# Header stripping
# ---------------------------------------------------------------------------
_HEADERS_TO_PRESERVE = {
    "content-type",
    "date",
    "content-encoding",
    "content-language",
    "last-modified",
    "location",
}


def strip_headers_hook(response, *args, **kwargs):
    """Strip response headers that override requests_cache behavior.

    Headers like ``Cache-Control`` cause requests_cache to re-fetch data that
    is already cached locally. Removing them lets the custom cache logic take
    precedence and avoids unnecessary network requests.
    """
    deleted = set()
    for header in list(response.headers.keys()):
        if header.lower() in _HEADERS_TO_PRESERVE:
            continue
        response.headers.pop(header, None)
        deleted.add(header)
    if deleted:
        logger.debug("Deleted headers: %s", ", ".join(deleted))
    return response


# ---------------------------------------------------------------------------
# Cached session factory
# ---------------------------------------------------------------------------
def create_cached_session(
    cache_options: dict[str, Any] | None = None,
    *,
    default_cache_name: str = "openbanking",
) -> requests.Session:
    """Return a :class:`requests.Session` with caching configured.

    If *cache_options* is ``None`` a plain (non-cached) session is returned.
    Otherwise a :class:`requests_cache.CachedSession` is built using sensible
    defaults merged with the user-supplied options.
    """
    if cache_options is None:
        return requests.Session()

    defaults = {**_DEFAULT_CACHE_OPTIONS, "cache_name": default_cache_name}
    defaults.update(cache_options)
    session = requests_cache.CachedSession(**defaults)
    session.hooks["response"].append(strip_headers_hook)
    return session


# ---------------------------------------------------------------------------
# Rate-limit retry helper
# ---------------------------------------------------------------------------
def send_with_rate_limit_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    max_retries: int = RATE_LIMIT_MAX_RETRIES,
    backoff_base: float = RATE_LIMIT_BACKOFF_BASE,
    **kwargs: Any,
) -> requests.Response:
    """Send a request with exponential back-off on HTTP 429.

    Retries up to *max_retries* times when the server returns ``429 Too Many
    Requests``. Uses the ``Retry-After`` header when available, otherwise
    falls back to exponential back-off.
    """
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


class BookingStatus(str, Enum):
    """Normalized booking state for imported transactions."""

    BOOKED = "booked"
    PENDING = "pending"


class TransactionDirection(str, Enum):
    """Normalized transaction direction."""

    CREDIT = "credit"
    DEBIT = "debit"


class Account(BaseModel):
    """Normalized account representation."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str | None = None
    currency: str | None = None
    iban: str | None = None
    provider_data: dict[str, Any] = Field(default_factory=dict)


class Balance(BaseModel):
    """Normalized balance representation."""

    model_config = ConfigDict(extra="allow")

    amount: str
    currency: str
    balance_type: str | None = None
    reference_date: str | None = None
    provider_data: dict[str, Any] = Field(default_factory=dict)


class Transaction(BaseModel):
    """Normalized transaction representation."""

    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    entry_reference: str | None = None
    booking_date: str | None = None
    value_date: str | None = None
    transaction_date: str | None = None
    amount: str
    currency: str
    direction: TransactionDirection | None = None
    booking_status: BookingStatus
    remittance_information: list[str] = Field(default_factory=list)
    creditor_name: str | None = None
    debtor_name: str | None = None
    provider_data: dict[str, Any] = Field(default_factory=dict)


class Provider(Protocol):
    """Protocol implemented by bank data providers."""

    def ensure_session(self) -> str: ...
    def list_accounts(self) -> list[Account]: ...
    def get_balances(self, account_id: str) -> list[Balance]: ...
    def get_transactions(
        self,
        account_id: str,
        booked_from: date | None = None,
        booked_to: date | None = None,
    ) -> list[Transaction]: ...
