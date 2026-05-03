"""Enable Banking provider."""

from __future__ import annotations

import logging
import secrets
import webbrowser
from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

from ..auth.callback_server import wait_for_oauth_callback
from ..auth.session_store import SessionStore
from .base import (
    Account,
    Balance,
    BookingStatus,
    Provider,
    Transaction,
    create_cached_session,
    send_with_rate_limit_retry,
)
from .enablebanking_types import (
    EnableBankingAccountDetail,
    EnableBankingBalance,
    EnableBankingSession,
    EnableBankingTransaction,
)
from .utils import normalize_booking_status, normalize_transaction_direction

logger = logging.getLogger(__name__)

BASE_URL = "https://api.enablebanking.com"
ENDPOINT_ASPSPS = "/aspsps"
ENDPOINT_AUTH = "/auth"
ENDPOINT_SESSIONS = "/sessions"
ENDPOINT_SESSION = "/sessions/{session_id}"
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
        self.timeout = timeout
        self.session_store = (
            SessionStore(session_store_path) if session_store_path is not None else None
        )
        self.http = create_cached_session(
            cache_options,
            default_cache_name="enablebanking",
        )

    def _require_session_store(self) -> SessionStore:
        if self.session_store is None:
            raise RuntimeError(
                "Enable Banking session storage is not configured. "
                "Set session_store_path to a writable directory."
            )
        return self.session_store

    def _headers(self) -> dict[str, str]:
        from ..auth.jwt_signing import build_auth_headers

        return build_auth_headers(self.application_id, self.private_key_path)

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        headers = kwargs.pop("headers", {})
        response = send_with_rate_limit_retry(
            self.http,
            method,
            f"{BASE_URL}{path}",
            headers={**self._headers(), **headers},
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def list_aspsps(self, country: str) -> list[dict[str, Any]]:
        return (
            self._request("GET", f"{ENDPOINT_ASPSPS}?country={country}")
            .json()
            .get("aspsps", [])
        )

    def start_authorization(
        self,
        aspsp_name: str,
        aspsp_country: str,
        psu_type: str = "personal",
        access_days: int = 90,
    ) -> dict[str, Any]:
        state = secrets.token_urlsafe(24)
        valid_until = (
            datetime.now(timezone.utc) + timedelta(days=access_days)
        ).isoformat()
        response = self._request(
            "POST",
            ENDPOINT_AUTH,
            json={
                "access": {"valid_until": valid_until},
                "aspsp": {"name": aspsp_name, "country": aspsp_country},
                "state": state,
                "redirect_url": self.redirect_url,
                "psu_type": psu_type,
            },
        )
        data = response.json()
        data["state"] = state
        return data

    def create_session_from_code(self, code: str) -> EnableBankingSession:
        raw = self._request("POST", ENDPOINT_SESSIONS, json={"code": code}).json()
        session_id = raw.get("session_id")
        if session_id:
            fresh = self._request(
                "GET",
                ENDPOINT_SESSION.format(session_id=session_id),
            ).json()
            raw = {**raw, **fresh}
        session = EnableBankingSession.from_api_response(raw)
        self._require_session_store().save(session)
        return session

    def authorize_interactive(
        self,
        aspsp_name: str,
        aspsp_country: str,
        callback_host: str = "127.0.0.1",
        callback_port: int = 8765,
        psu_type: str = "personal",
        access_days: int = 90,
        open_browser: bool = True,
    ) -> EnableBankingSession:
        authorization = self.start_authorization(
            aspsp_name=aspsp_name,
            aspsp_country=aspsp_country,
            psu_type=psu_type,
            access_days=access_days,
        )
        expected_state = authorization["state"]
        authorization_url = authorization["url"]

        if open_browser:
            webbrowser.open(authorization_url)
        else:
            print(authorization_url)

        result = wait_for_oauth_callback(host=callback_host, port=callback_port)
        if result.state != expected_state:
            raise RuntimeError("OAuth state mismatch - possible CSRF attack")
        if result.error:
            raise RuntimeError(
                f"OAuth authorization failed: {result.error} - {result.error_description}"
            )
        if not result.code:
            raise RuntimeError("No authorization code received")
        return self.create_session_from_code(result.code)

    def ensure_session(self) -> str:
        session_store = self._require_session_store()
        if not session_store.exists():
            raise RuntimeError(
                "No Enable Banking session found. "
                "Run authorize_interactive() first to establish a session."
            )
        session_ids = session_store.list()
        if not session_ids:
            raise RuntimeError(
                "No Enable Banking session found. "
                "Run authorize_interactive() first to establish a session."
            )
        return session_ids[0]

    def get_session(self, session_id: str) -> EnableBankingSession:
        raw = self._request(
            "GET", ENDPOINT_SESSION.format(session_id=session_id)
        ).json()
        return EnableBankingSession.from_api_response(raw)

    def delete_session(self, session_id: str) -> None:
        """Delete a session locally and revoke it at the ASPSP."""
        try:
            self._request("DELETE", ENDPOINT_SESSION.format(session_id=session_id))
        except Exception:
            pass
        self._require_session_store().delete(session_id)

    def list_sessions(self) -> list[EnableBankingSession]:
        """Return all stored sessions with fresh API data."""
        session_store = self._require_session_store()
        stored = session_store.load_all()
        sessions: list[EnableBankingSession] = []
        for session in stored:
            sid = session.session_id
            if not sid:
                continue
            try:
                fresh = self.get_session(sid)
                merged = EnableBankingSession.model_validate(
                    {**session.model_dump(), **fresh.model_dump()}
                )
                session_store.save(merged)
                sessions.append(merged)
            except Exception:
                sessions.append(session)
        return sessions

    def list_accounts(self) -> list[Account]:
        sessions = self.list_sessions()
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
                        resp = self._request("GET", f"/accounts/{uid}/details")
                        detail = EnableBankingAccountDetail.model_validate(resp.json())
                    except Exception:
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
        raw_response = self._request(
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

            raw_response = self._request(
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
