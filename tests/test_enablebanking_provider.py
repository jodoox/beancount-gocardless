"""Tests for the Enable Banking provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from beancount_openbanking.auth.enablebanking_types import (
    EnableBankingAccountDetail,
    EnableBankingSession,
)
from beancount_openbanking.providers import (
    BookingStatus,
    EnableBankingProvider,
    TransactionDirection,
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

        with patch.object(provider.api, "request", return_value=response):
            banks = provider.list_aspsps("FR")

        assert banks == [{"name": "Hello Bank"}]

    def test_list_accounts_empty(self) -> None:
        provider = EnableBankingProvider(
            application_id="test-app",
            private_key_path="/path/to/key.pem",
            redirect_url="http://localhost/callback",
            session_store_path="/tmp/test-sessions",
        )
        provider.session_manager.list_sessions = MagicMock(return_value=[])

        assert provider.list_accounts() == []

    def test_list_accounts_with_data(self) -> None:
        provider = EnableBankingProvider(
            application_id="test-app",
            private_key_path="/path/to/key.pem",
            redirect_url="http://localhost/callback",
            session_store_path="/tmp/test-sessions",
        )
        provider.session_manager.list_sessions = MagicMock(
            return_value=[
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
        )

        accounts = provider.list_accounts()

        assert len(accounts) == 1
        assert accounts[0].id == "acc-1"
        assert accounts[0].iban == "DE89370400440532013000"

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
            provider.api,
            "request",
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
