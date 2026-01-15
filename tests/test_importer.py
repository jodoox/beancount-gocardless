import pytest
from unittest.mock import Mock, patch
from datetime import date, timedelta
from beancount.core import data
from beancount_gocardless.importer import GoCardLessImporter
from beancount_gocardless.models import (
    AccountBalance,
    BalanceSchema,
    BalanceAmountSchema,
)


@pytest.fixture
def importer():
    imp = GoCardLessImporter()
    imp.config = Mock()
    imp.config.secret_id = "test_id"
    imp.config.secret_key = "test_key"
    imp.config.cache_options = {}

    mock_account = Mock()
    mock_account.id = "ACC1"
    mock_account.asset_account = "Assets:Bank:Test"
    mock_account.metadata = {"test": "meta"}
    mock_account.transaction_types = ["booked"]

    imp.config.accounts = [mock_account]
    return imp


def test_extract_balance_assertion_priority(importer):
    """Test that balance assertion uses prioritized types."""
    with patch("beancount_gocardless.importer.GoCardlessClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value

        # Mock transactions (empty)
        mock_tx_resp = Mock()
        mock_tx_resp.transactions = {"booked": []}
        mock_client.get_account_transactions.return_value = mock_tx_resp

        # Mock balances - no 'expected', but has 'interimAvailable'
        mock_balances = AccountBalance(
            balances=[
                BalanceSchema(
                    balance_amount=BalanceAmountSchema(amount="100.00", currency="EUR"),
                    balance_type="interimAvailable",
                    reference_date="2026-01-15",
                )
            ]
        )
        mock_client.get_account_balances.return_value = mock_balances

        # We need to set the internal client to our mock
        importer._client = mock_client
        importer.load_config = Mock()

        entries = importer.extract("gocardless.yaml", [])

        # Should have one entry: the balance assertion
        balance_entries = [e for e in entries if isinstance(e, data.Balance)]
        assert len(balance_entries) == 1
        assert balance_entries[0].account == "Assets:Bank:Test"
        assert balance_entries[0].amount.number == 100
        # Date should be reference_date + 1 day
        assert balance_entries[0].date == date(2026, 1, 16)
        assert balance_entries[0].meta["test"] == "meta"
        assert "interimAvailable: 100.00 EUR" in balance_entries[0].meta["detail"]


def test_extract_balance_assertion_multiple_distinct(importer):
    """Test that balance assertion shows all distinct balance values."""
    with patch("beancount_gocardless.importer.GoCardlessClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_tx_resp = Mock()
        mock_tx_resp.transactions = {"booked": []}
        mock_client.get_account_transactions.return_value = mock_tx_resp

        # Multiple balances with different values
        mock_balances = AccountBalance(
            balances=[
                BalanceSchema(
                    balance_amount=BalanceAmountSchema(amount="100.00", currency="EUR"),
                    balance_type="expected",
                    reference_date="2026-01-15",
                ),
                BalanceSchema(
                    balance_amount=BalanceAmountSchema(amount="105.00", currency="EUR"),
                    balance_type="interimAvailable",
                    reference_date="2026-01-15",
                ),
                BalanceSchema(
                    balance_amount=BalanceAmountSchema(amount="100.00", currency="EUR"),
                    balance_type="closingBooked",
                    reference_date="2026-01-15",
                ),
            ]
        )
        mock_client.get_account_balances.return_value = mock_balances
        importer._client = mock_client
        importer.load_config = Mock()

        entries = importer.extract("gocardless.yaml", [])

        balance_entries = [e for e in entries if isinstance(e, data.Balance)]
        assert len(balance_entries) == 1
        assert balance_entries[0].amount.number == 100
        # Detail should contain expected and interimAvailable, but NOT closingBooked (as it has same value as expected)
        detail = balance_entries[0].meta["detail"]
        assert "expected: 100.00 EUR" in detail
        assert "interimAvailable: 105.00 EUR" in detail
        assert "closingBooked" not in detail


def test_extract_balance_assertion_preferred(importer):
    """Test that balance assertion respects preferred_balance_type."""
    with patch("beancount_gocardless.importer.GoCardlessClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_tx_resp = Mock()
        mock_tx_resp.transactions = {"booked": []}
        mock_client.get_account_transactions.return_value = mock_tx_resp

        # Multiple balances, interimAvailable is preferred
        mock_balances = AccountBalance(
            balances=[
                BalanceSchema(
                    balance_amount=BalanceAmountSchema(amount="100.00", currency="EUR"),
                    balance_type="expected",
                    reference_date="2026-01-15",
                ),
                BalanceSchema(
                    balance_amount=BalanceAmountSchema(amount="105.00", currency="EUR"),
                    balance_type="interimAvailable",
                    reference_date="2026-01-15",
                ),
            ]
        )
        mock_client.get_account_balances.return_value = mock_balances
        importer._client = mock_client
        importer.load_config = Mock()

        # Set preferred balance type in config
        importer.config.accounts[0].preferred_balance_type = "interimAvailable"

        entries = importer.extract("gocardless.yaml", [])

        balance_entries = [e for e in entries if isinstance(e, data.Balance)]
        assert len(balance_entries) == 1
        # Should use interimAvailable (105.00) even though expected (100.00) exists
        assert balance_entries[0].amount.number == 105
        assert "interimAvailable: 105.00 EUR" in balance_entries[0].meta["detail"]
