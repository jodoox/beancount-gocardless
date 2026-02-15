"""
GoCardless Bank Account Data API client.

Typed client with Pydantic models, response caching via requests-cache,
and automatic token management.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
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

    def __init__(
        self,
        secret_id: str,
        secret_key: str,
        cache_options: Optional[Dict[str, Any]] = None,
    ):
        logger.info("Initializing GoCardlessClient")
        self.secret_id = secret_id
        self.secret_key = secret_key
        self._token: Optional[str] = None

        # Default cache options that match the original client
        default_cache_options = {
            "cache_name": "gocardless",
            "backend": "sqlite",
            "expire_after": 0,
            "old_data_on_error": True,
            "match_headers": False,
            "cache_control": False,
        }

        # Merge with provided options
        cache_config = {**default_cache_options, **(cache_options or {})}
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
            except Exception as e:
                logger.error(
                    f"Error checking expiration for cache key {cache_key}: {e}"
                )
                is_expired = None

        return {
            "key_exists": key_exists,
            "is_expired": is_expired,
            "cache_key": cache_key,
        }

    @property
    def token(self) -> str:
        """
        Get or refresh access token.
        """
        if not self._token:
            self.get_token()
        return self._token

    def get_token(self):
        """
        Fetch a new API access token using credentials.
        """
        logger.debug("Fetching new access token")
        response = requests.post(
            f"{self.BASE_URL}/token/new/",
            data={"secret_id": self.secret_id, "secret_key": self.secret_key},
        )
        response.raise_for_status()
        self._token = response.json()["access"]
        logger.debug("Access token obtained")

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Send an authenticated request, retrying once on 401 after token refresh."""
        url = f"{self.BASE_URL}{endpoint}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"

        # Check cache status for logging
        status = self.check_cache_status(
            method, url, kwargs.get("params"), kwargs.get("data")
        )
        logger.debug(
            f"{endpoint}: {'expired' if status.get('is_expired') else 'cache ok'}"
        )

        response = self.session.request(method, url, headers=headers, **kwargs)
        logger.debug("Response headers: %s", response.headers)

        # Handle 401 by refreshing token
        if response.status_code == 401:
            self.get_token()
            headers["Authorization"] = f"Bearer {self.token}"
            response = self.session.request(method, url, headers=headers, **kwargs)

        response.raise_for_status()
        return response

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
        data = self.get(f"/accounts/{account_id}/")
        return Account(**data)

    def get_account_balances(self, account_id: str) -> AccountBalance:
        """Retrieve balances for a single account."""
        logger.debug("Getting account balances for %s", account_id)
        data = self.get(f"/accounts/{account_id}/balances/")
        return AccountBalance(**data)

    def get_account_details(self, account_id: str) -> AccountDetail:
        """Retrieve detailed information for a single account."""
        logger.debug("Getting account details for %s", account_id)
        data = self.get(f"/accounts/{account_id}/details/")
        return AccountDetail(**data)

    def get_account_transactions(
        self, account_id: str, days_back: int = 180
    ) -> AccountTransactions:
        """Retrieve transactions for an account within a date range.

        Args:
            account_id: GoCardless account UUID.
            days_back: Number of days of history to fetch (default 180).

        Returns:
            An ``AccountTransactions`` object containing booked and pending lists.
        """
        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        date_to = datetime.now().strftime("%Y-%m-%d")
        logger.debug(
            "Fetching transactions for account %s from %s to %s",
            account_id,
            date_from,
            date_to,
        )

        data = self.get(
            f"/accounts/{account_id}/transactions/",
            params={"date_from": date_from, "date_to": date_to},
        )
        booked_count = len(data.get("transactions", {}).get("booked", []))
        pending_count = len(data.get("transactions", {}).get("pending", []))
        logger.debug(
            "Fetched %d booked and %d pending transactions for account %s",
            booked_count,
            pending_count,
            account_id,
        )
        return AccountTransactions(**data)

    # Institutions methods
    def get_institutions(self, country: Optional[str] = None) -> List[Institution]:
        """List available banking institutions, optionally filtered by country code."""
        logger.debug("Getting institutions for country %s", country)
        params = {"country": country} if country else {}
        institutions_data = self.get("/institutions/", params=params)
        logger.debug("Fetched %d institutions", len(institutions_data))
        return [Institution(**inst) for inst in institutions_data]

    def get_institution(self, institution_id: str) -> Institution:
        """Retrieve a single institution by its ID."""
        data = self.get(f"/institutions/{institution_id}/")
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
        data = self.post("/requisitions/", data=request_data)
        return Requisition(**data)

    def get_requisitions(self) -> List[Requisition]:
        """List all requisitions."""
        logger.debug("Getting all requisitions")
        data = self.get("/requisitions/")
        logger.debug("Fetched %d requisitions", len(data.get("results", [])))
        return [Requisition(**req) for req in data.get("results", [])]

    def get_requisition(self, requisition_id: str) -> Requisition:
        """Retrieve a single requisition by its ID."""
        data = self.get(f"/requisitions/{requisition_id}/")
        return Requisition(**data)

    def delete_requisition(self, requisition_id: str) -> Dict[str, Any]:
        """Delete a requisition by its ID."""
        return self.delete(f"/requisitions/{requisition_id}/")

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
        data = self.post("/agreements/enduser/", data=request_data)
        return EndUserAgreement(**data)

    def get_agreements(self) -> List[EndUserAgreement]:
        """List all end-user agreements."""
        data = self.get("/agreements/enduser/")
        return [EndUserAgreement(**ag) for ag in data.get("results", [])]

    def get_agreement(self, agreement_id: str) -> EndUserAgreement:
        """Retrieve a single end-user agreement by its ID."""
        data = self.get(f"/agreements/enduser/{agreement_id}/")
        return EndUserAgreement(**data)

    def accept_agreement(
        self, agreement_id: str, user_agent: str, ip: str
    ) -> Dict[str, Any]:
        """Accept an end-user agreement."""
        data = self.post(
            f"/agreements/enduser/{agreement_id}/accept/",
            data={"user_agent": user_agent, "ip": ip},
        )
        return data

    def reconfirm_agreement(
        self, agreement_id: str, user_agent: str, ip: str
    ) -> ReconfirmationRetrieve:
        """Reconfirm an end-user agreement."""
        data = self.post(
            f"/agreements/enduser/{agreement_id}/reconfirm/",
            data={"user_agent": user_agent, "ip": ip},
        )
        return ReconfirmationRetrieve(**data)

    # Token management endpoints (usually handled internally)
    def get_access_token(self) -> SpectacularJWTObtain:
        """Obtain a new JWT access token. Usually handled internally by the client."""
        data = self.post(
            "/token/new/",
            data={"secret_id": self.secret_id, "secret_key": self.secret_key},
        )
        return SpectacularJWTObtain(**data)

    def refresh_access_token(self, refresh_token: str) -> SpectacularJWTRefresh:
        """Refresh an existing JWT access token."""
        data = self.post("/token/refresh/", data={"refresh": refresh_token})
        return SpectacularJWTRefresh(**data)

    # Integration endpoints
    def get_integrations(self) -> List[Integration]:
        """List all integrations."""
        data = self.get("/integrations/")
        return [Integration(**integration) for integration in data]

    def get_integration(self, integration_id: str) -> Integration:
        """Retrieve a single integration by its ID."""
        data = self.get(f"/integrations/{integration_id}/")
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
        data = self.get("/requisitions/", params=params)
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
        data = self.get("/agreements/enduser/", params=params)
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
                except Exception:
                    # Skip accounts that can't be accessed
                    continue
        return accounts

    def list_accounts(self) -> List[AccountInfo]:
        """Alias for :meth:`get_all_accounts`."""
        return self.get_all_accounts()
