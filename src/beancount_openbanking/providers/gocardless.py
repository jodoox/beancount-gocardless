"""GoCardless Bank Account Data provider."""

from __future__ import annotations

import argparse
import logging
import time
from datetime import date
from typing import Any

import requests

from .base import (
    Account,
    Balance,
    BookingStatus,
    Provider,
    Transaction,
)
from .http import create_cached_session, send_with_rate_limit_retry
from .gocardless_types import Institution, Requisition
from .utils import normalize_transaction_direction

logger = logging.getLogger(__name__)

BASE_URL = "https://bankaccountdata.gocardless.com/api/v2"
ENDPOINT_TOKEN_NEW = "/token/new/"
ENDPOINT_ACCOUNTS = "/accounts/{account_id}/"
ENDPOINT_ACCOUNT_BALANCES = "/accounts/{account_id}/balances/"
ENDPOINT_ACCOUNT_TRANSACTIONS = "/accounts/{account_id}/transactions/"
ENDPOINT_INSTITUTIONS = "/institutions/"
ENDPOINT_REQUISITIONS = "/requisitions/"
ENDPOINT_REQUISITION = "/requisitions/{requisition_id}/"


class GoCardlessProvider(Provider):
    """Fetch normalized account data through the GoCardless API."""

    def __init__(
        self,
        secret_id: str,
        secret_key: str,
        cache_options: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> None:
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.timeout = timeout
        self._token: str | None = None
        self._token_expires_at = 0.0
        self.http = create_cached_session(
            cache_options,
            default_cache_name="gocardless",
        )

    @classmethod
    def from_config(cls, config: object) -> "GoCardlessProvider":
        """Build a provider from a parsed ``GoCardlessConfig``."""
        # Local import to avoid a circular dependency at module load time.
        from ..config import GoCardlessConfig

        assert isinstance(config, GoCardlessConfig)
        return cls(
            secret_id=config.secret_id,
            secret_key=config.secret_key,
            cache_options=config.cache_options or None,
        )

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "GoCardlessProvider":
        """Build a provider from already-validated CLI arguments."""
        return cls(
            secret_id=args.secret_id,
            secret_key=args.secret_key,
        )

    @staticmethod
    def credentials_from_args(args: argparse.Namespace) -> tuple[str, str] | None:
        """Return ``(secret_id, secret_key)`` if present, else ``None``."""
        sid = getattr(args, "secret_id", None)
        skey = getattr(args, "secret_key", None)
        if not sid or not skey:
            return None
        return sid, skey

    @property
    def token(self) -> str:
        if not self._token or time.monotonic() > self._token_expires_at:
            self._refresh_token()
        assert self._token is not None
        return self._token

    def _refresh_token(self) -> None:
        response = self.http.post(
            f"{BASE_URL}{ENDPOINT_TOKEN_NEW}",
            data={"secret_id": self.secret_id, "secret_key": self.secret_key},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = time.monotonic() + expires_in - 30

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> requests.Response:
        response = send_with_rate_limit_retry(
            self.http,
            method,
            f"{BASE_URL}{endpoint}",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def _get(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._request("GET", endpoint, params=params).json()

    def _get_requisitions(self) -> list[dict[str, Any]]:
        return self._get(ENDPOINT_REQUISITIONS).get("results", [])

    def _get_account(self, account_id: str) -> dict[str, Any]:
        return self._get(ENDPOINT_ACCOUNTS.format(account_id=account_id))

    def list_institutions(self, country: str | None = None) -> list[Institution]:
        params = {"country": country} if country else None
        raw_institutions = self._get(ENDPOINT_INSTITUTIONS, params=params)
        return [Institution.model_validate(item) for item in raw_institutions]

    def list_requisitions(self) -> list[Requisition]:
        raw_requisitions = self._get(ENDPOINT_REQUISITIONS).get("results", [])
        return [Requisition.model_validate(item) for item in raw_requisitions]

    def create_requisition(
        self,
        redirect_url: str,
        institution_id: str,
        reference: str,
        **kwargs: Any,
    ) -> Requisition:
        payload = {
            "redirect": redirect_url,
            "institution_id": institution_id,
            "reference": reference,
        }
        payload.update(kwargs)
        response = self._request("POST", ENDPOINT_REQUISITIONS, data=payload)
        return Requisition.model_validate(response.json())

    def delete_requisition(self, requisition_id: str) -> None:
        self._request(
            "DELETE", ENDPOINT_REQUISITION.format(requisition_id=requisition_id)
        )

    def list_accounts(self) -> list[Account]:
        accounts: list[Account] = []
        for requisition in self._get_requisitions():
            for account_id in requisition.get("accounts", []):
                try:
                    raw = self._get_account(account_id)
                except requests.RequestException:
                    logger.warning("Failed to load GoCardless account %s", account_id)
                    continue

                raw["requisition_id"] = requisition.get("id")
                raw["requisition_reference"] = requisition.get("reference")
                raw["institution_id"] = requisition.get("institution_id")
                iban = raw.get("iban")
                accounts.append(
                    Account(
                        id=raw.get("id", ""),
                        name=raw.get("name"),
                        currency=iban_to_currency(iban),
                        iban=iban,
                        provider_data=raw,
                    )
                )
        return accounts

    def get_balances(self, account_id: str) -> list[Balance]:
        raw_response = self._get(
            ENDPOINT_ACCOUNT_BALANCES.format(account_id=account_id)
        )
        balances: list[Balance] = []
        for raw in raw_response.get("balances", []):
            amount = raw.get("balanceAmount", {})
            balances.append(
                Balance(
                    amount=str(amount.get("amount", "0")),
                    currency=amount.get("currency", ""),
                    balance_type=raw.get("balanceType"),
                    reference_date=raw.get("referenceDate"),
                    provider_data=raw,
                )
            )
        return balances

    def get_transactions(
        self,
        account_id: str,
        booked_from: date | None = None,
        booked_to: date | None = None,
    ) -> list[Transaction]:
        params: dict[str, str] = {}
        if booked_from:
            params["date_from"] = booked_from.isoformat()
        if booked_to:
            params["date_to"] = booked_to.isoformat()

        raw_response = self._get(
            ENDPOINT_ACCOUNT_TRANSACTIONS.format(account_id=account_id),
            params=params or None,
        )
        transactions = raw_response.get("transactions", {})

        result: list[Transaction] = []
        for raw in transactions.get("booked", []):
            result.append(self._normalize_transaction(raw, BookingStatus.BOOKED))
        for raw in transactions.get("pending", []):
            result.append(self._normalize_transaction(raw, BookingStatus.PENDING))
        return result

    def _normalize_transaction(
        self,
        raw: dict[str, Any],
        booking_status: BookingStatus,
    ) -> Transaction:
        amount = raw.get("transactionAmount") or raw.get("transaction_amount") or {}

        remittance_information: list[str] = []
        unstructured = raw.get("remittanceInformationUnstructured") or raw.get(
            "remittance_information_unstructured"
        )
        if unstructured:
            remittance_information.append(unstructured)
        unstructured_array = raw.get(
            "remittanceInformationUnstructuredArray"
        ) or raw.get("remittance_information_unstructured_array")
        if unstructured_array:
            remittance_information.extend(unstructured_array)

        return Transaction(
            transaction_id=coalesce_field(raw, "transactionId", "transaction_id"),
            entry_reference=coalesce_field(raw, "entryReference", "entry_reference"),
            booking_date=coalesce_field(raw, "bookingDate", "booking_date"),
            value_date=coalesce_field(raw, "valueDate", "value_date"),
            transaction_date=coalesce_field(
                raw,
                "transactionDate",
                "transaction_date",
                "bookingDate",
                "booking_date",
            ),
            amount=str(amount.get("amount", "0")),
            currency=amount.get("currency", ""),
            direction=normalize_transaction_direction(
                coalesce_field(raw, "creditDebitIndicator", "credit_debit_indicator")
            ),
            booking_status=booking_status,
            remittance_information=remittance_information,
            creditor_name=coalesce_field(raw, "creditorName", "creditor_name"),
            debtor_name=coalesce_field(raw, "debtorName", "debtor_name"),
            provider_data=raw,
        )


# ---------------------------------------------------------------------------
# GoCardless-specific helpers
# ---------------------------------------------------------------------------


def coalesce_field(raw: dict[str, Any], *keys: str) -> Any:
    """Return the first non-``None`` value among the given keys."""
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return value
    return None


IBAN_CURRENCY_MAP: dict[str, str] = {
    "AL": "ALL",
    "AD": "EUR",
    "AT": "EUR",
    "AZ": "AZN",
    "BH": "BHD",
    "BY": "BYN",
    "BE": "EUR",
    "BA": "BAM",
    "BR": "BRL",
    "BG": "BGN",
    "CR": "CRC",
    "HR": "EUR",
    "CY": "EUR",
    "CZ": "CZK",
    "DK": "DKK",
    "DO": "DOP",
    "EG": "EGP",
    "SV": "USD",
    "EE": "EUR",
    "FI": "EUR",
    "FR": "EUR",
    "GE": "GEL",
    "DE": "EUR",
    "GI": "GIP",
    "GR": "EUR",
    "GT": "GTQ",
    "HU": "HUF",
    "IS": "ISK",
    "IE": "EUR",
    "IL": "ILS",
    "IT": "EUR",
    "JO": "JOD",
    "KZ": "KZT",
    "KW": "KWD",
    "LV": "EUR",
    "LB": "LBP",
    "LI": "CHF",
    "LT": "EUR",
    "LU": "EUR",
    "MT": "EUR",
    "MR": "MRU",
    "MU": "MUR",
    "MD": "MDL",
    "MC": "EUR",
    "ME": "EUR",
    "NL": "EUR",
    "MK": "MKD",
    "NO": "NOK",
    "PK": "PKR",
    "PS": "ILS",
    "PL": "PLN",
    "PT": "EUR",
    "RO": "RON",
    "LC": "XCD",
    "SM": "EUR",
    "SA": "SAR",
    "RS": "RSD",
    "SC": "SCR",
    "SK": "EUR",
    "SI": "EUR",
    "ES": "EUR",
    "SE": "SEK",
    "CH": "CHF",
    "TN": "TND",
    "TR": "TRY",
    "UA": "UAH",
    "AE": "AED",
    "GB": "GBP",
    "VA": "EUR",
    "VG": "USD",
    "XK": "EUR",
}


def iban_to_currency(iban: str | None) -> str | None:
    """Infer a currency from the IBAN country prefix."""
    if not iban or len(iban) < 2:
        return None
    return IBAN_CURRENCY_MAP.get(iban[:2].upper())
