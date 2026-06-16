"""Enable Banking provider."""

from __future__ import annotations

import argparse
import logging
from datetime import date
from typing import Any, Callable

import requests

from ..auth.api_client import EnableBankingApiClient
from ..auth.enablebanking_types import EnableBankingAccountDetail, EnableBankingSession
from ..auth.session_manager import SessionManager
from ..auth.session_store import SessionStore
from .base import (
    Account,
    Balance,
    BookingStatus,
    Provider,
    Transaction,
)
from .enablebanking_types import (
    EnableBankingBalance,
    EnableBankingTransaction,
)
from .http import create_cached_session
from .utils import normalize_transaction_direction

logger = logging.getLogger(__name__)

ENDPOINT_ASPSPS = "/aspsps"
ENDPOINT_ACCOUNT_BALANCES = "/accounts/{account_id}/balances"
ENDPOINT_ACCOUNT_TRANSACTIONS = "/accounts/{account_id}/transactions"


class EnableBankingProvider(Provider):
    """Fetch normalized account data through Enable Banking."""

    def __init__(
        self,
        application_id: str,
        private_key_path: str,
        redirect_url: str,
        session_store_path: str | None = None,
        timeout: int = 30,
        cache_options: dict[str, Any] | None = None,
    ) -> None:
        self.application_id = application_id
        self.private_key_path = private_key_path
        self.redirect_url = redirect_url
        self.http = create_cached_session(
            cache_options,
            default_cache_name="enablebanking",
        )
        self.api = EnableBankingApiClient(
            http=self.http,
            build_headers=self._build_headers,
            timeout=timeout,
        )
        self.session_manager = SessionManager(
            http=self.http,
            build_headers=self._build_headers,
            session_store=(
                SessionStore(session_store_path)
                if session_store_path is not None
                else None
            ),
            redirect_url=redirect_url,
            timeout=timeout,
        )

    @classmethod
    def from_config(cls, config: object) -> "EnableBankingProvider":
        """Build a provider from a parsed ``EnableBankingConfig``."""
        from ..config import EnableBankingConfig

        assert isinstance(config, EnableBankingConfig)
        return cls(
            application_id=config.application_id,
            private_key_path=config.private_key_path,
            redirect_url=config.redirect_url,
            session_store_path=config.session_store_path,
        )

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "EnableBankingProvider":
        """Build a provider from already-validated CLI arguments."""
        return cls(
            application_id=args.application_id,
            private_key_path=args.private_key_path,
            redirect_url=args.redirect_url,
            session_store_path=args.session_store_path,
        )

    @staticmethod
    def credentials_from_args(args: argparse.Namespace) -> tuple[str, str] | None:
        """Return ``(application_id, private_key_path)`` if present, else ``None``."""
        app_id = getattr(args, "application_id", None)
        key_path = getattr(args, "private_key_path", None)
        if not app_id or not key_path:
            return None
        return app_id, key_path

    def _build_headers(self) -> dict[str, str]:
        from ..auth.jwt_signing import build_auth_headers

        return build_auth_headers(self.application_id, self.private_key_path)

    def list_sessions(self) -> list[EnableBankingSession]:
        """Return all stored sessions, refreshed from the API.

        Delegates to :class:`~..auth.session_manager.SessionManager`. Exposed
        here so the rest of the codebase talks to the provider, not its
        internal session manager.
        """
        return self.session_manager.list_sessions()

    def delete_session(self, session_id: str) -> None:
        """Delete a session locally and revoke it at the ASPSP.

        Delegates to :class:`~..auth.session_manager.SessionManager`.
        """
        self.session_manager.delete_session(session_id)

    def authorize_interactive(
        self,
        aspsp_name: str,
        aspsp_country: str,
        callback_host: str = "127.0.0.1",
        callback_port: int = 8765,
        psu_type: str = "personal",
        access_days: int = 90,
        open_browser: bool = True,
        on_authorization_url: Callable[[str], None] | None = None,
    ) -> EnableBankingSession:
        """Run the OAuth authorization flow interactively.

        Delegates to :class:`~..auth.session_manager.SessionManager`.
        """
        return self.session_manager.authorize_interactive(
            aspsp_name=aspsp_name,
            aspsp_country=aspsp_country,
            callback_host=callback_host,
            callback_port=callback_port,
            psu_type=psu_type,
            access_days=access_days,
            open_browser=open_browser,
            on_authorization_url=on_authorization_url,
        )

    def list_aspsps(self, country: str) -> list[dict[str, Any]]:
        return (
            self.api.request("GET", f"{ENDPOINT_ASPSPS}?country={country}")
            .json()
            .get("aspsps", [])
        )

    def list_accounts(self) -> list[Account]:
        sessions = self.session_manager.list_sessions()
        if not sessions:
            return []

        result: list[Account] = []
        seen_uids: set[str] = set()

        for session in sessions:
            data_by_uid = {detail.uid: detail for detail in session.accounts_data}

            for uid in session.accounts:
                if uid in seen_uids:
                    continue
                seen_uids.add(uid)

                detail = data_by_uid.get(uid)
                if not detail or not detail.name:
                    try:
                        resp = self.api.request("GET", f"/accounts/{uid}/details")
                        detail = EnableBankingAccountDetail.model_validate(resp.json())
                    except requests.RequestException as exc:
                        logger.debug("Could not fetch details for %s: %s", uid, exc)
                        detail = None

                if detail:
                    result.append(
                        Account(
                            id=uid,
                            name=detail.name,
                            currency=detail.currency,
                            iban=detail.account_id.iban if detail.account_id else None,
                            provider_data=detail.model_dump(),
                        )
                    )
                else:
                    result.append(Account(id=uid))

        return result

    def get_balances(self, account_id: str) -> list[Balance]:
        raw_response = self.api.request(
            "GET",
            ENDPOINT_ACCOUNT_BALANCES.format(account_id=account_id),
        ).json()
        balances: list[Balance] = []
        for raw in raw_response.get("balances", []):
            balance = EnableBankingBalance.model_validate(raw)
            balances.append(
                Balance(
                    amount=balance.balance_amount.amount,
                    currency=balance.balance_amount.currency,
                    balance_type=balance.balance_type,
                    reference_date=balance.reference_date,
                    provider_data=balance.model_dump(),
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

        transactions: list[Transaction] = []
        seen_transactions: set[tuple[str | None, str | None, str, str, str | None]] = (
            set()
        )
        continuation_key: str | None = None
        while True:
            current = dict(params)
            if continuation_key:
                current["continuation_key"] = continuation_key

            raw_response = self.api.request(
                "GET",
                ENDPOINT_ACCOUNT_TRANSACTIONS.format(account_id=account_id),
                params=current or None,
            ).json()

            for raw in raw_response.get("transactions", []):
                transaction = self._normalize_transaction(raw)
                identity = self._transaction_identity(transaction)
                if identity in seen_transactions:
                    continue
                seen_transactions.add(identity)
                transactions.append(transaction)

            continuation_key = raw_response.get("continuation_key")
            if not continuation_key:
                break

        return transactions

    def _transaction_identity(
        self,
        transaction: Transaction,
    ) -> tuple[str | None, str | None, str, str, str | None]:
        return (
            transaction.transaction_id,
            transaction.entry_reference,
            transaction.amount,
            transaction.currency,
            transaction.booking_date or transaction.value_date,
        )

    def _normalize_transaction(self, raw: dict[str, Any]) -> Transaction:
        tx = EnableBankingTransaction.model_validate(raw)

        remittance_information = list(tx.remittance_information)
        if not remittance_information and tx.remittance_information_unstructured:
            remittance_information = [tx.remittance_information_unstructured]
        if not remittance_information and tx.remittance_information_unstructured_array:
            remittance_information = list(tx.remittance_information_unstructured_array)

        return Transaction(
            transaction_id=tx.transaction_id,
            entry_reference=tx.entry_reference,
            booking_date=tx.booking_date,
            value_date=tx.value_date,
            transaction_date=tx.transaction_date or tx.booking_date,
            amount=tx.transaction_amount.amount,
            currency=tx.transaction_amount.currency,
            direction=normalize_transaction_direction(tx.credit_debit_indicator),
            booking_status=normalize_booking_status(
                tx.status,
                default=BookingStatus.BOOKED,
            )
            or BookingStatus.BOOKED,
            remittance_information=remittance_information,
            creditor_name=tx.creditor_name,
            debtor_name=tx.debtor_name,
            provider_data=raw,
        )


def normalize_booking_status(
    value: str | None,
    *,
    default: BookingStatus | None = None,
) -> BookingStatus | None:
    """Normalize provider-specific booking status codes."""
    if value is None:
        return default
    normalized = value.upper()
    if normalized in {"BOOK", "BOOKED"}:
        return BookingStatus.BOOKED
    if normalized in {"PDNG", "PENDING"}:
        return BookingStatus.PENDING
    return default
