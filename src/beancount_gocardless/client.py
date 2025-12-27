"""
GoCardless Bank Account Data API Client
Clean, typed, auto-generated client with full caching and header stripping
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
    Institution,
    Requisition,
    EndUserAgreement,
    ReconfirmationRetrieve,
    PaginatedRequisitionList,
    PaginatedEndUserAgreementList,
    Integration,
    IntegrationRetrieve,
    SpectacularJWTObtain,
    SpectacularJWTRefresh,
    AccountInfo,
)

logger = logging.getLogger(__name__)


def strip_headers_hook(response, *args, **kwargs):
    """
    Strip response headers to reduce cache size and improve privacy.
    Only preserves essential headers needed for proper operation.
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
    """
    Clean, typed GoCardless Bank Account Data API client with full caching support.
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

        # Create cached session with header stripping
        self.session = requests_cache.CachedSession(**cache_config)
        self.session.hooks["response"].append(strip_headers_hook)

    def check_cache_status(self, method: str, url: str, params=None, data=None) -> dict:
        """
        Check cache status for a given request.
        This mimics the original client's cache checking functionality.
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
        """Make authenticated request with caching"""
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
        """Make GET request"""
        response = self._request("GET", endpoint, params=params)
        return response.json()

    def post(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make POST request"""
        response = self._request("POST", endpoint, data=data)
        return response.json()

    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make DELETE request"""
        response = self._request("DELETE", endpoint)
        return response.json()

    # Account methods
    def get_account(self, account_id: str) -> Account:
        """Get account metadata"""
        logger.debug("Getting account metadata for %s", account_id)
        data = self.get(f"/accounts/{account_id}/")
        return Account(**data)

    def get_account_balances(self, account_id: str) -> AccountBalance:
        """Get account balances"""
        logger.debug("Getting account balances for %s", account_id)
        data = self.get(f"/accounts/{account_id}/balances/")
        return AccountBalance(**data)

    def get_account_details(self, account_id: str) -> AccountDetail:
        """Get account details"""
        logger.debug("Getting account details for %s", account_id)
        data = self.get(f"/accounts/{account_id}/details/")
        return AccountDetail(**data)

    def get_account_transactions(
        self, account_id: str, days_back: int = 180
    ) -> AccountTransactions:
        """Get account transactions"""
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
        """Get institutions for a country"""
        logger.debug("Getting institutions for country %s", country)
        params = {"country": country} if country else {}
        institutions_data = self.get("/institutions/", params=params)
        logger.debug("Fetched %d institutions", len(institutions_data))
        return [Institution(**inst) for inst in institutions_data]

    def get_institution(self, institution_id: str) -> Institution:
        """Get specific institution"""
        data = self.get(f"/institutions/{institution_id}/")
        return Institution(**data)

    # Requisitions methods
    def create_requisition(
        self, redirect: str, institution_id: str, reference: str, **kwargs
    ) -> Requisition:
        """Create a new requisition"""
        request_data = {
            "redirect": redirect,
            "institution_id": institution_id,
            "reference": reference,
        }
        request_data.update(kwargs)
        data = self.post("/requisitions/", data=request_data)
        return Requisition(**data)

    def get_requisitions(self) -> List[Requisition]:
        """Get all requisitions"""
        logger.debug("Getting all requisitions")
        data = self.get("/requisitions/")
        logger.debug("Fetched %d requisitions", len(data.get("results", [])))
        return [Requisition(**req) for req in data.get("results", [])]

    def get_requisition(self, requisition_id: str) -> Requisition:
        """Get specific requisition"""
        data = self.get(f"/requisitions/{requisition_id}/")
        return Requisition(**data)

    def delete_requisition(self, requisition_id: str) -> Dict[str, Any]:
        """Delete a requisition"""
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
        """Create end user agreement"""
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
        """Get all agreements"""
        data = self.get("/agreements/enduser/")
        return [EndUserAgreement(**ag) for ag in data.get("results", [])]

    def get_agreement(self, agreement_id: str) -> EndUserAgreement:
        """Get specific agreement"""
        data = self.get(f"/agreements/enduser/{agreement_id}/")
        return EndUserAgreement(**data)

    def accept_agreement(
        self, agreement_id: str, user_agent: str, ip: str
    ) -> Dict[str, Any]:
        """Accept an agreement"""
        data = self.post(
            f"/agreements/enduser/{agreement_id}/accept/",
            data={"user_agent": user_agent, "ip": ip},
        )
        return data

    def reconfirm_agreement(
        self, agreement_id: str, user_agent: str, ip: str
    ) -> ReconfirmationRetrieve:
        """Reconfirm an agreement"""
        data = self.post(
            f"/agreements/enduser/{agreement_id}/reconfirm/",
            data={"user_agent": user_agent, "ip": ip},
        )
        return ReconfirmationRetrieve(**data)

    # Token management endpoints (usually handled internally)
    def get_access_token(self) -> SpectacularJWTObtain:
        """Get a new access token (usually handled internally)"""
        data = self.post(
            "/token/new/",
            data={"secret_id": self.secret_id, "secret_key": self.secret_key},
        )
        return SpectacularJWTObtain(**data)

    def refresh_access_token(self, refresh_token: str) -> SpectacularJWTRefresh:
        """Refresh access token"""
        data = self.post("/token/refresh/", data={"refresh": refresh_token})
        return SpectacularJWTRefresh(**data)

    # Integration endpoints
    def get_integrations(self) -> List[Integration]:
        """Get all integrations"""
        data = self.get("/integrations/")
        return [Integration(**integration) for integration in data]

    def get_integration(self, integration_id: str) -> IntegrationRetrieve:
        """Get specific integration"""
        data = self.get(f"/integrations/{integration_id}/")
        return IntegrationRetrieve(**data)

    # Paginated endpoints with full response models
    def get_requisitions_paginated(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> PaginatedRequisitionList:
        """Get paginated requisitions"""
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
        """Get paginated agreements"""
        params = {}
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        data = self.get("/agreements/enduser/", params=params)
        return PaginatedEndUserAgreementList(**data)

    # Convenience methods for common workflows
    def list_banks(self, country: Optional[str] = None) -> List[str]:
        """Quick way to list bank names for a country"""
        institutions = self.get_institutions(country)
        return [inst.name for inst in institutions]

    def find_requisition_by_reference(self, reference: str) -> Optional[Requisition]:
        """Find a requisition by its reference"""
        requisitions = self.get_requisitions()
        return next((req for req in requisitions if req.reference == reference), None)

    def create_bank_link(
        self, reference: str, bank_id: str, redirect_url: str = "http://localhost"
    ) -> Optional[str]:
        """Create bank link and return the URL"""
        existing = self.find_requisition_by_reference(reference)
        if existing:
            return None

        requisition = self.create_requisition(
            redirect=redirect_url, institution_id=bank_id, reference=reference
        )
        return requisition.link

    def get_all_accounts(self) -> List[AccountInfo]:
        """Get all accounts from all requisitions"""
        accounts = []
        for req in self.get_requisitions():
            for account_id in req.accounts:
                try:
                    account = self.get_account(account_id)
                    account_dict = account.model_dump()
                    account_dict.update(
                        {
                            "requisition_id": req.id,
                            "requisition_reference": req.reference,
                            "institution_id": req.institution_id,
                        }
                    )
                    accounts.append(account_dict)
                except Exception:
                    # Skip accounts that can't be accessed
                    continue
        return accounts

    def list_accounts(self) -> List[AccountInfo]:
        """Alias for get_all_accounts"""
        return self.get_all_accounts()
