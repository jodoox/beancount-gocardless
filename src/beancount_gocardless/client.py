"""GoCardless Bank Account Data API client.

Wraps the GoCardless REST API with Pydantic models and SQLite-backed response
caching (via requests-cache).
"""

import logging
import time
from typing import Optional, Dict, Any, List, TypedDict, cast
from datetime import date, datetime, timedelta
import requests_cache
import requests
from .models import (
    Account,
    AccountBalance,
    AccountDetail,
    AccountTransactions,
    AccountInfo,
    EndUserAgreement,
    Institution,
    Integration,
    PaginatedEndUserAgreementList,
    PaginatedRequisitionList,
    ReconfirmationRetrieve,
    Requisition,
    SpectacularJWTObtain,
    SpectacularJWTRefresh,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# API endpoint constants
# ---------------------------------------------------------------------------
ENDPOINT_TOKEN_NEW = "/token/new/"
ENDPOINT_TOKEN_REFRESH = "/token/refresh/"
ENDPOINT_ACCOUNTS = "/accounts/{account_id}/"
ENDPOINT_ACCOUNT_BALANCES = "/accounts/{account_id}/balances/"
ENDPOINT_ACCOUNT_DETAILS = "/accounts/{account_id}/details/"
ENDPOINT_ACCOUNT_TRANSACTIONS = "/accounts/{account_id}/transactions/"
ENDPOINT_INSTITUTIONS = "/institutions/"
ENDPOINT_INSTITUTION = "/institutions/{institution_id}/"
ENDPOINT_REQUISITIONS = "/requisitions/"
ENDPOINT_REQUISITION = "/requisitions/{requisition_id}/"
ENDPOINT_AGREEMENTS = "/agreements/enduser/"
ENDPOINT_AGREEMENT = "/agreements/enduser/{agreement_id}/"
ENDPOINT_AGREEMENT_ACCEPT = "/agreements/enduser/{agreement_id}/accept/"
ENDPOINT_AGREEMENT_RECONFIRM = "/agreements/enduser/{agreement_id}/reconfirm/"
ENDPOINT_INTEGRATIONS = "/integrations/"
ENDPOINT_INTEGRATION = "/integrations/{integration_id}/"

# ---------------------------------------------------------------------------
# Pagination / retry limits
# ---------------------------------------------------------------------------
MAX_PAGINATION_PAGES = 100
RATE_LIMIT_MAX_RETRIES = 3
RATE_LIMIT_BACKOFF_BASE = 1  # seconds

__all__ = [
    "GoCardlessClient",
    "CacheOptions",
    "strip_headers_hook",
    "ENDPOINT_TOKEN_NEW",
    "MAX_PAGINATION_PAGES",
    "RATE_LIMIT_MAX_RETRIES",
]


def strip_headers_hook(response, *args, **kwargs):
    """Strip response headers that override requests_cache behavior.

    Headers like Cache-Control cause requests_cache to re-fetch data that is
    already cached locally. Removing them lets the custom cache logic take
    precedence and avoids unnecessary network requests.
    """
    to_preserve = [
        "Content-Type",
        "Date",
        "Content-Encoding",
        "Content-Language",
        "Last-Modified",
        "Location",
    ]
    deleted = set()
    to_preserve_lower = [h.lower() for h in to_preserve]
    header_keys_to_check = response.headers.copy().keys()
    for header in header_keys_to_check:
        if header.lower() in to_preserve_lower:
            continue
        else:
            response.headers.pop(header, None)
            deleted.add(header)
    logger.debug("Deleted headers: %s", ", ".join(deleted))
    return response


class CacheOptions(TypedDict, total=False):
    cache_name: str
    backend: str
    expire_after: int
    old_data_on_error: bool
    match_headers: bool
    cache_control: bool


class GoCardlessClient:
    """GoCardless Bank Account Data API client.

    Wraps the GoCardless (formerly Nordigen) REST API with typed return values
    (Pydantic models), optional SQLite-backed response caching, and automatic
    JWT token acquisition/refresh.

    Args:
        secret_id: GoCardless API secret ID.
        secret_key: GoCardless API secret key.
        cache_options: Optional dict of keyword arguments forwarded to
            ``requests_cache.CachedSession``. If ``None``, default caching
            settings are used (SQLite backend, no expiry).
    """

    BASE_URL = "https://bankaccountdata.gocardless.com/api/v2"

    #: Seconds to subtract from token lifetime to account for clock skew.
    _TOKEN_EXPIRY_BUFFER: int = 30

    def __init__(
        self,
        secret_id: str,
        secret_key: str,
        cache_options: Optional[CacheOptions] = None,
    ):
        logger.info("Initializing GoCardlessClient")
        self.secret_id = secret_id
        self.secret_key = secret_key
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

        default_cache_options: CacheOptions = {
            "cache_name": "gocardless",
            "backend": "sqlite",
            "expire_after": 0,
            "old_data_on_error": True,
            "match_headers": False,
            "cache_control": False,
        }

        # Merge with provided options
        cache_config: CacheOptions = {**default_cache_options, **(cache_options or {})}
        logger.debug("Cache config: %s", cache_config)

        # Create cached session; strip response headers to prevent cache bypasses
        self.session = requests_cache.CachedSession(**cache_config)
        self.session.hooks["response"].append(strip_headers_hook)

    def check_cache_status(self, method: str, url: str, params=None, data=None) -> dict:
        """Check whether a cached response exists for the given request.

        Args:
            method: HTTP method (e.g. ``"GET"``).
            url: Full request URL.
            params: Optional query parameters.
            data: Optional request body data.

        Returns:
            Dict with keys ``key_exists`` (bool), ``is_expired`` (bool or None),
            and ``cache_key`` (str).
        """
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}

        req = requests.Request(method, url, params=params, data=data, headers=headers)
        prepared_request: requests.PreparedRequest = self.session.prepare_request(req)
        cache = self.session.cache
        cache_key = cache.create_key(prepared_request)
        key_exists = cache.contains(cache_key)
        is_expired = None

        if key_exists:
            try:
                cached_response = cache.get_response(cache_key)
                if cached_response:
                    is_expired = cached_response.is_expired
                else:
                    key_exists = False
                    is_expired = True
            except (requests.RequestException, KeyError, AttributeError) as e:
                logger.error(
                    "Error checking expiration for cache key %s: %s",
                    cache_key,
                    e,
                )
                is_expired = None

        return {
            "key_exists": key_exists,
            "is_expired": is_expired,
            "cache_key": cache_key,
        }

    @property
    def token(self) -> str:
        """Return a valid access token, refreshing if expired or missing."""
        if not self._token or time.monotonic() >= self._token_expires_at:
            self.get_token()
        assert self._token is not None
        return self._token

    def get_token(self):
        """Fetch a new API access token using credentials."""
        logger.debug("Fetching new access token")
        response = requests.post(
            f"{self.BASE_URL}{ENDPOINT_TOKEN_NEW}",
            data={"secret_id": self.secret_id, "secret_key": self.secret_key},
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access"]
        expires_in = data.get("access_expires", 86400)
        self._token_expires_at = (
            time.monotonic() + expires_in - self._TOKEN_EXPIRY_BUFFER
        )
        logger.debug("Access token obtained, expires in %ds", expires_in)

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Send an authenticated request with 401 retry and rate-limit handling."""
        url = f"{self.BASE_URL}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"

        # Check cache status for logging
        status = self.check_cache_status(
            method, url, kwargs.get("params"), kwargs.get("data")
        )
        logger.debug(
            "%s: %s",
            endpoint,
            "expired" if status.get("is_expired") else "cache ok",
        )

        response = self._request_with_rate_limit(method, url, headers, **kwargs)
        logger.debug("Response headers: %s", response.headers)

        # Handle 401 by refreshing token and retrying once
        if response.status_code == 401:
            self.get_token()
            headers["Authorization"] = f"Bearer {self.token}"
            response = self._request_with_rate_limit(method, url, headers, **kwargs)

        response.raise_for_status()
        return response

    def _request_with_rate_limit(
        self, method: str, url: str, headers: dict, **kwargs
    ) -> requests.Response:
        """Execute a request with exponential back-off on 429 responses.

        Retries up to ``RATE_LIMIT_MAX_RETRIES`` times when the server returns
        HTTP 429 (Too Many Requests). Uses the ``Retry-After`` header when
        available, otherwise falls back to exponential back-off.
        """
        attempt = 0
        while True:
            response = self.session.request(method, url, headers=headers, **kwargs)
            if response.status_code != 429:
                return response
            if attempt >= RATE_LIMIT_MAX_RETRIES:
                return response
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    wait = float(retry_after)
                except (ValueError, TypeError):
                    wait = RATE_LIMIT_BACKOFF_BASE * (2**attempt)
            else:
                wait = RATE_LIMIT_BACKOFF_BASE * (2**attempt)
            logger.warning(
                "Rate limited (429). Retrying in %.1f seconds (attempt %d/%d)",
                wait,
                attempt + 1,
                RATE_LIMIT_MAX_RETRIES,
            )
            time.sleep(wait)
            attempt += 1

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Send a GET request and return the JSON response body."""
        response = self._request("GET", endpoint, params=params)
        return response.json()

    def post(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Send a POST request and return the JSON response body."""
        response = self._request("POST", endpoint, data=data)
        return response.json()

    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Send a DELETE request and return the JSON response body."""
        response = self._request("DELETE", endpoint)
        return response.json()

    # Account methods
    def get_account(self, account_id: str) -> Account:
        """Retrieve metadata for a single account."""
        logger.debug("Getting account metadata for %s", account_id)
        data = self.get(ENDPOINT_ACCOUNTS.format(account_id=account_id))
        return Account(**data)

    def get_account_balances(self, account_id: str) -> AccountBalance:
        """Retrieve balances for a single account."""
        logger.debug("Getting account balances for %s", account_id)
        data = self.get(ENDPOINT_ACCOUNT_BALANCES.format(account_id=account_id))
        return AccountBalance(**data)

    def get_account_details(self, account_id: str) -> AccountDetail:
        """Retrieve detailed information for a single account."""
        logger.debug("Getting account details for %s", account_id)
        data = self.get(ENDPOINT_ACCOUNT_DETAILS.format(account_id=account_id))
        return AccountDetail(**data)

    def get_account_transactions(
        self, account_id: str, days_back: int = 180
    ) -> AccountTransactions:
        """Retrieve transactions for an account within a date range.

        Follows pagination links to fetch all available pages, up to
        ``MAX_PAGINATION_PAGES`` pages to prevent infinite loops.

        Args:
            account_id: GoCardless account UUID.
            days_back: Number of days of history to fetch (default 180).

        Returns:
            AccountTransactions with all booked and pending transactions.
        """
        date_from = (date.today() - timedelta(days=days_back)).isoformat()
        date_to = date.today().isoformat()
        logger.debug(
            "Fetching transactions for account %s from %s to %s",
            account_id,
            date_from,
            date_to,
        )

        data = self.get(
            ENDPOINT_ACCOUNT_TRANSACTIONS.format(account_id=account_id),
            params={"date_from": date_from, "date_to": date_to},
        )

        all_booked = list(data.get("transactions", {}).get("booked", []))
        all_pending = list(data.get("transactions", {}).get("pending", []))

        # Follow pagination links if present (with max-page guard)
        next_url = data.get("next")
        page_count = 0
        while next_url and page_count < MAX_PAGINATION_PAGES:
            page_count += 1
            # next_url is an absolute URL; strip the base to get the endpoint
            if next_url.startswith(self.BASE_URL):
                endpoint = next_url[len(self.BASE_URL) :]
            else:
                endpoint = next_url
            try:
                page_data = self.get(endpoint)
            except Exception:
                logger.exception(
                    "Failed to fetch transaction page %d for account %s",
                    page_count,
                    account_id,
                )
                raise
            all_booked.extend(page_data.get("transactions", {}).get("booked", []))
            all_pending.extend(page_data.get("transactions", {}).get("pending", []))
            next_url = page_data.get("next")

        if page_count >= MAX_PAGINATION_PAGES:
            logger.warning(
                "Pagination limit reached (%d pages) for account %s",
                MAX_PAGINATION_PAGES,
                account_id,
            )
        logger.debug(
            "Fetched %d booked and %d pending transactions for account %s",
            len(all_booked),
            len(all_pending),
            account_id,
        )

        return AccountTransactions(
            transactions={"booked": all_booked, "pending": all_pending}
        )

    # Institutions methods
    def get_institutions(self, country: Optional[str] = None) -> List[Institution]:
        """List available banking institutions, optionally filtered by country code."""
        logger.debug("Getting institutions for country %s", country)
        params = {"country": country} if country else {}
        institutions_data = cast(
            List[Dict[str, Any]], self.get(ENDPOINT_INSTITUTIONS, params=params)
        )
        logger.debug("Fetched %d institutions", len(institutions_data))
        return [Institution(**inst) for inst in institutions_data]

    def get_institution(self, institution_id: str) -> Institution:
        """Retrieve a single institution by its ID."""
        data = self.get(ENDPOINT_INSTITUTION.format(institution_id=institution_id))
        return Institution(**data)

    # Requisitions methods
    def create_requisition(
        self, redirect: str, institution_id: str, reference: str, **kwargs
    ) -> Requisition:
        """Create a new requisition (bank authorization request).

        Args:
            redirect: URL the user is redirected to after authorization.
            institution_id: ID of the banking institution.
            reference: A unique reference string for this requisition.
            **kwargs: Additional fields forwarded to the API.
        """
        request_data = {
            "redirect": redirect,
            "institution_id": institution_id,
            "reference": reference,
        }
        request_data.update(kwargs)
        data = self.post(ENDPOINT_REQUISITIONS, data=request_data)
        return Requisition(**data)

    def get_requisitions(self) -> List[Requisition]:
        """List all requisitions."""
        logger.debug("Getting all requisitions")
        data = self.get(ENDPOINT_REQUISITIONS)
        logger.debug("Fetched %d requisitions", len(data.get("results", [])))
        return [Requisition(**req) for req in data.get("results", [])]

    def get_requisition(self, requisition_id: str) -> Requisition:
        """Retrieve a single requisition by its ID."""
        data = self.get(ENDPOINT_REQUISITION.format(requisition_id=requisition_id))
        return Requisition(**data)

    def delete_requisition(self, requisition_id: str) -> Dict[str, Any]:
        """Delete a requisition by its ID."""
        return self.delete(ENDPOINT_REQUISITION.format(requisition_id=requisition_id))

    # Agreements methods
    def create_agreement(
        self,
        institution_id: str,
        max_historical_days: int,
        access_valid_for_days: int,
        access_scope: List[str],
        **kwargs,
    ) -> EndUserAgreement:
        """Create an end-user agreement for a given institution.

        Args:
            institution_id: ID of the banking institution.
            max_historical_days: Maximum number of days of transaction history.
            access_valid_for_days: Number of days the access is valid.
            access_scope: List of access scopes (e.g. ``["balances", "details", "transactions"]``).
            **kwargs: Additional fields forwarded to the API.
        """
        request_data = {
            "institution_id": institution_id,
            "max_historical_days": max_historical_days,
            "access_valid_for_days": access_valid_for_days,
            "access_scope": access_scope,
        }
        request_data.update(kwargs)
        data = self.post(ENDPOINT_AGREEMENTS, data=request_data)
        return EndUserAgreement(**data)

    def get_agreements(self) -> List[EndUserAgreement]:
        """List all end-user agreements."""
        data = self.get(ENDPOINT_AGREEMENTS)
        return [EndUserAgreement(**ag) for ag in data.get("results", [])]

    def get_agreement(self, agreement_id: str) -> EndUserAgreement:
        """Retrieve a single end-user agreement by its ID."""
        data = self.get(ENDPOINT_AGREEMENT.format(agreement_id=agreement_id))
        return EndUserAgreement(**data)

    def accept_agreement(
        self, agreement_id: str, user_agent: str, ip: str
    ) -> Dict[str, Any]:
        """Accept an end-user agreement."""
        data = self.post(
            ENDPOINT_AGREEMENT_ACCEPT.format(agreement_id=agreement_id),
            data={"user_agent": user_agent, "ip": ip},
        )
        return data

    def reconfirm_agreement(
        self, agreement_id: str, user_agent: str, ip: str
    ) -> ReconfirmationRetrieve:
        """Reconfirm an end-user agreement."""
        data = self.post(
            ENDPOINT_AGREEMENT_RECONFIRM.format(agreement_id=agreement_id),
            data={"user_agent": user_agent, "ip": ip},
        )
        return ReconfirmationRetrieve(**data)

    # Token management endpoints (usually handled internally)
    def get_access_token(self) -> SpectacularJWTObtain:
        """Obtain a new JWT access token. Usually handled internally by the client."""
        data = self.post(
            ENDPOINT_TOKEN_NEW,
            data={"secret_id": self.secret_id, "secret_key": self.secret_key},
        )
        return SpectacularJWTObtain(**data)

    def refresh_access_token(self, refresh_token: str) -> SpectacularJWTRefresh:
        """Refresh an existing JWT access token."""
        data = self.post(ENDPOINT_TOKEN_REFRESH, data={"refresh": refresh_token})
        return SpectacularJWTRefresh(**data)

    # Integration endpoints
    def get_integrations(self) -> List[Integration]:
        """List all integrations."""
        data = cast(List[Dict[str, Any]], self.get(ENDPOINT_INTEGRATIONS))
        return [Integration(**d) for d in data]

    def get_integration(self, integration_id: str) -> Integration:
        """Retrieve a single integration by its ID."""
        data = self.get(ENDPOINT_INTEGRATION.format(integration_id=integration_id))
        return Integration(**data)

    # Paginated endpoints with full response models
    def get_requisitions_paginated(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> PaginatedRequisitionList:
        """List requisitions with pagination support."""
        params = {}
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        data = self.get(ENDPOINT_REQUISITIONS, params=params)
        return PaginatedRequisitionList(**data)

    def get_agreements_paginated(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> PaginatedEndUserAgreementList:
        """List end-user agreements with pagination support."""
        params = {}
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        data = self.get(ENDPOINT_AGREEMENTS, params=params)
        return PaginatedEndUserAgreementList(**data)

    # Convenience methods for common workflows
    def list_banks(self, country: Optional[str] = None) -> List[str]:
        """Return a list of bank names, optionally filtered by country code."""
        institutions = self.get_institutions(country)
        return [inst.name for inst in institutions]

    def find_requisition_by_reference(self, reference: str) -> Optional[Requisition]:
        """Find a requisition by its reference string, or return ``None``."""
        requisitions = self.get_requisitions()
        return next((req for req in requisitions if req.reference == reference), None)

    def create_bank_link(
        self, reference: str, bank_id: str, redirect_url: str = "http://localhost"
    ) -> Optional[str]:
        """Create a bank authorization link and return the URL.

        Returns ``None`` if a requisition with the same reference already exists.
        """
        existing = self.find_requisition_by_reference(reference)
        if existing:
            return None

        requisition = self.create_requisition(
            redirect=redirect_url, institution_id=bank_id, reference=reference
        )
        return requisition.link

    def get_all_accounts(self) -> List[AccountInfo]:
        """Collect all accounts across all requisitions, with expiry metadata."""
        accounts = []
        for req in self.get_requisitions():
            for account_id in req.accounts:
                try:
                    account = self.get_account(account_id)
                    account_dict = account.model_dump()

                    access_valid_days = req.access_valid_for_days or 90
                    created_date = datetime.fromisoformat(
                        req.created.replace("Z", "+00:00")
                    )
                    expiry_date = created_date + timedelta(days=access_valid_days)
                    is_expired = req.status == "EX"

                    account_dict.update(
                        {
                            "requisition_id": req.id,
                            "requisition_reference": req.reference,
                            "institution_id": req.institution_id,
                            "requisition_status": req.status,
                            "access_valid_until": expiry_date.isoformat(),
                            "is_expired": is_expired,
                        }
                    )
                    accounts.append(account_dict)
                except requests.RequestException:
                    # Skip accounts that can't be accessed due to network errors
                    continue
        return accounts

    def list_accounts(self) -> List[AccountInfo]:
        """Alias for :meth:`get_all_accounts`."""
        return self.get_all_accounts()
