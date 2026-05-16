"""Tests for normalized provider models and helpers."""

from __future__ import annotations

from beancount_openbanking.importer import BALANCE_TYPE_PRIORITY
from beancount_openbanking.providers import (
    Account,
    Balance,
    BookingStatus,
    Transaction,
    TransactionDirection,
)
from beancount_openbanking.providers.gocardless import coalesce_field, iban_to_currency


class TestProviderDomainModels:
    def test_account_model(self) -> None:
        account = Account(
            id="account-1",
            name="Checking",
            currency="EUR",
            iban="DE89370400440532013000",
            provider_data={"id": "account-1"},
        )
        assert account.id == "account-1"
        assert account.currency == "EUR"

    def test_balance_model(self) -> None:
        balance = Balance(
            amount="1000.00",
            currency="EUR",
            balance_type="closingBooked",
            reference_date="2024-01-15",
            provider_data={"balanceType": "closingBooked"},
        )
        assert balance.balance_type == "closingBooked"
        assert balance.reference_date == "2024-01-15"

    def test_transaction_model(self) -> None:
        transaction = Transaction(
            transaction_id="tx-123",
            entry_reference="ref-456",
            booking_date="2024-01-15",
            value_date="2024-01-16",
            transaction_date="2024-01-15",
            amount="-50.00",
            currency="EUR",
            direction=TransactionDirection.DEBIT,
            booking_status=BookingStatus.BOOKED,
            remittance_information=["Test payment"],
            creditor_name="Test Creditor",
            provider_data={"transactionId": "tx-123"},
        )
        assert transaction.booking_status == BookingStatus.BOOKED
        assert transaction.direction == TransactionDirection.DEBIT


class TestProviderUtils:
    def test_coalesce_field(self) -> None:
        assert coalesce_field({"a": None, "b": "value"}, "a", "b") == "value"
        assert coalesce_field({}, "a", "b") is None

    def test_iban_to_currency(self) -> None:
        assert iban_to_currency("DE89370400440532013000") == "EUR"
        assert iban_to_currency("GB29NWBK60161331926819") == "GBP"
        assert iban_to_currency(None) is None

    def test_balance_priority_contains_provider_variants(self) -> None:
        assert (
            BALANCE_TYPE_PRIORITY["closingBooked"] == BALANCE_TYPE_PRIORITY["CLOSING"]
        )
