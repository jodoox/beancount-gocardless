"""Tests for the Enable Banking provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from beancount_openbanking.providers import (
    BookingStatus,
    EnableBankingProvider,
    TransactionDirection,
)
from beancount_openbanking.providers.enablebanking_types import (
    EnableBankingAccountDetail,
    EnableBankingSession,
)


class TestEnableBankingProvider:
    @patch("beancount_openbanking.providers.enablebanking.create_cached_session")
    def test_passes_cache_options_to_cached_session(self, mock_create_session) -> None:
        EnableBankingProvider(
            application_id="test-app",
            private_key_path="/path/to/key.pem",
            redirect_url="http://localhost/callback",
            cache_options={"cache_name": "test-cache"},
        )

        mock_create_session.assert_called_once_with(
            {"cache_name": "test-cache"},
            default_cache_name="enablebanking",
        )

    @patch("beancount_openbanking.providers.enablebanking.create_cached_session")
    def test_empty_cache_options_enables_caching(self, mock_create_session) -> None:
        provider = EnableBankingProvider(
            application_id="test-app",
            private_key_path="/path/to/key.pem",
            redirect_url="http://localhost/callback",
            cache_options={},
        )

        mock_create_session.assert_called_once_with(
            {},
            default_cache_name="enablebanking",
        )
        assert provider.http is mock_create_session.return_value

    def test_none_cache_options_disables_caching(self) -> None:
        import requests

        provider = EnableBankingProvider(
            application_id="test-app",
            private_key_path="/path/to/key.pem",
            redirect_url="http://localhost/callback",
            cache_options=None,
        )

        assert isinstance(provider.http, requests.Session)
        assert (
            not isinstance(provider.http, type(provider.http))
            or "CachedSession" not in type(provider.http).__name__
        )

    def test_provider_allows_bank_listing_without_session_store(self) -> None:
        provider = EnableBankingProvider(
            application_id="test-app",
            private_key_path="/path/to/key.pem",
            redirect_url="http://localhost/callback",
            session_store_path=None,
        )

        response = MagicMock()
        response.json.return_value = {"aspsps": [{"name": "Hello Bank"}]}

        with patch.object(provider, "_request", return_value=response):
            banks = provider.list_aspsps("FR")

        assert banks == [{"name": "Hello Bank"}]

    def test_session_methods_require_session_store(self) -> None:
        provider = EnableBankingProvider(
            application_id="test-app",
            private_key_path="/path/to/key.pem",
            redirect_url="http://localhost/callback",
            session_store_path=None,
        )

        with pytest.raises(RuntimeError, match="session storage is not configured"):
            provider.list_sessions()

    @patch("beancount_openbanking.auth.session_store.SessionStore")
    def test_create_session_from_code_refreshes_session_details(
        self, mock_store_cls
    ) -> None:
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store

        provider = EnableBankingProvider(
            application_id="test-app",
            private_key_path="/path/to/key.pem",
            redirect_url="http://localhost/callback",
            session_store_path="/tmp/test-sessions",
        )
        provider.session_store = mock_store
        post_response = MagicMock()
        post_response.json.return_value = {"session_id": "session-1"}
        get_response = MagicMock()
        get_response.json.return_value = {
            "session_id": "session-1",
            "accounts": [{"uid": "acc-1", "name": "Checking"}],
        }

        with patch.object(
            provider,
            "_request",
            side_effect=[post_response, get_response],
        ):
            session = provider.create_session_from_code("auth-code")

        assert isinstance(session, EnableBankingSession)
        assert session.accounts[0] == "acc-1"
        mock_store.save.assert_called_once()
        saved = mock_store.save.call_args[0][0]
        assert isinstance(saved, EnableBankingSession)

    @patch("beancount_openbanking.auth.session_store.SessionStore")
    def test_list_accounts_empty(self, mock_store_cls) -> None:
        mock_store = MagicMock()
        mock_store.load_all.return_value = []
        mock_store.exists.return_value = False
        mock_store.list.return_value = []
        mock_store_cls.return_value = mock_store

        provider = EnableBankingProvider(
            application_id="test-app",
            private_key_path="/path/to/key.pem",
            redirect_url="http://localhost/callback",
            session_store_path="/tmp/test-sessions",
        )
        provider.session_store = mock_store

        assert provider.list_accounts() == []

    @patch("beancount_openbanking.auth.session_store.SessionStore")
    def test_list_accounts_with_data(self, mock_store_cls) -> None:
        mock_store = MagicMock()
        mock_store.load_all.return_value = [
            EnableBankingSession(
                session_id="session-1",
                accounts=["acc-1"],
                accounts_data=[
                    EnableBankingAccountDetail(
                        uid="acc-1",
                        name="Test Account",
                        currency="EUR",
                        account_id={"iban": "DE89370400440532013000"},
                    )
                ],
            )
        ]
        mock_store_cls.return_value = mock_store

        provider = EnableBankingProvider(
            application_id="test-app",
            private_key_path="/path/to/key.pem",
            redirect_url="http://localhost/callback",
            session_store_path="/tmp/test-sessions",
        )
        provider.session_store = mock_store

        accounts = provider.list_accounts()

        assert len(accounts) == 1
        assert accounts[0].id == "acc-1"
        assert accounts[0].iban == "DE89370400440532013000"

    @patch("beancount_openbanking.auth.session_store.SessionStore")
    def test_list_accounts_refreshes_stored_session(self, mock_store_cls) -> None:
        mock_store = MagicMock()
        mock_store.load_all.return_value = [
            EnableBankingSession(session_id="session-1")
        ]
        mock_store_cls.return_value = mock_store

        provider = EnableBankingProvider(
            application_id="test-app",
            private_key_path="/path/to/key.pem",
            redirect_url="http://localhost/callback",
            session_store_path="/tmp/test-sessions",
        )
        provider.session_store = mock_store

        with patch.object(
            provider,
            "get_session",
            return_value=EnableBankingSession(
                session_id="session-1",
                accounts=["acc-1"],
                accounts_data=[
                    EnableBankingAccountDetail(
                        uid="acc-1",
                        name="Checking",
                    )
                ],
            ),
        ):
            accounts = provider.list_accounts()

        assert len(accounts) == 1
        assert accounts[0].id == "acc-1"
        mock_store.save.assert_called_once()

    @patch("beancount_openbanking.auth.session_store.SessionStore")
    def test_get_transactions_does_not_duplicate_entries(self, mock_store_cls) -> None:
        mock_store_cls.return_value = MagicMock()

        provider = EnableBankingProvider(
            application_id="test-app",
            private_key_path="/path/to/key.pem",
            redirect_url="http://localhost/callback",
            session_store_path="/tmp/test-sessions",
        )

        first_response = MagicMock()
        first_response.json.return_value = {
            "transactions": [
                {
                    "transaction_id": "tx-1",
                    "booking_date": "2024-01-15",
                    "transaction_amount": {"amount": "-50.00", "currency": "EUR"},
                    "credit_debit_indicator": "DBIT",
                    "creditor_name": "Test Creditor",
                    "remittance_information": ["Test payment"],
                    "status": "BOOK",
                }
            ],
            "continuation_key": "page-2",
        }
        second_response = MagicMock()
        second_response.json.return_value = {
            "transactions": [
                {
                    "transaction_id": "tx-1",
                    "booking_date": "2024-01-15",
                    "transaction_amount": {"amount": "-50.00", "currency": "EUR"},
                    "credit_debit_indicator": "DBIT",
                    "creditor_name": "Test Creditor",
                    "remittance_information": ["Test payment"],
                    "status": "BOOK",
                },
                {
                    "transaction_id": "tx-2",
                    "booking_date": "2024-01-16",
                    "transaction_amount": {"amount": "-10.00", "currency": "EUR"},
                    "credit_debit_indicator": "DBIT",
                    "creditor_name": "Test Creditor",
                    "remittance_information": ["Another payment"],
                    "status": "BOOK",
                },
            ]
        }
        with patch.object(
            provider,
            "_request",
            side_effect=[first_response, second_response],
        ):
            transactions = provider.get_transactions("acc-1")

        assert len(transactions) == 2
        assert [transaction.transaction_id for transaction in transactions] == [
            "tx-1",
            "tx-2",
        ]
        assert transactions[0].booking_status == BookingStatus.BOOKED
        assert transactions[0].direction == TransactionDirection.DEBIT
