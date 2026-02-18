import pytest
from unittest.mock import Mock, patch
from datetime import date
from beancount.core import data
from beancount_gocardless.importer import GoCardlessImporter
from beancount_gocardless.models import (
    AccountBalance,
    BalanceAfterTransactionSchema,
    BalanceSchema,
    BalanceAmountSchema,
    BankTransaction,
    TransactionAmountSchema,
    AccountConfig,
)


@pytest.fixture
def importer():
    imp = GoCardlessImporter()
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

        entries = importer.extract("gocardless.yaml", existing=[])

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

        entries = importer.extract("gocardless.yaml", existing=[])

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

        entries = importer.extract("gocardless.yaml", existing=[])

        balance_entries = [e for e in entries if isinstance(e, data.Balance)]
        assert len(balance_entries) == 1
        # Should use interimAvailable (105.00) even though expected (100.00) exists
        assert balance_entries[0].amount.number == 105
        assert "interimAvailable: 105.00 EUR" in balance_entries[0].meta["detail"]


def test_add_metadata_exclude_specific_fields(importer):
    """Test that specific default metadata fields can be excluded."""
    transaction = BankTransaction(
        transaction_id="TX123",
        creditor_name="Test Creditor",
        debtor_name="Test Debtor",
        booking_date="2026-01-15",
        transaction_amount=TransactionAmountSchema(amount="100.00", currency="EUR"),
    )

    config = AccountConfig(
        id="ACC1",
        asset_account="Assets:Test",
        exclude_default_metadata=["creditorName", "bookingDate"],
    )

    metadata = importer.add_metadata(transaction, {}, config)

    assert metadata["nordref"] == "TX123"
    assert metadata["debtorName"] == "Test Debtor"
    assert "creditorName" not in metadata
    assert "bookingDate" not in metadata


def test_add_metadata_custom_fields(importer):
    """Test that custom metadata fields can be added via metadata_fields."""
    transaction = BankTransaction(
        transaction_id="TX123",
        creditor_name="Test Creditor",
        debtor_name="Test Debtor",
        booking_date="2026-01-15",
        transaction_amount=TransactionAmountSchema(amount="100.00", currency="EUR"),
        merchant_category_code="5411",
        ultimate_creditor="Store Inc",
    )

    config = AccountConfig(
        id="ACC1",
        asset_account="Assets:Test",
        metadata_fields={
            "ref": "transactionId",
            "payee": "creditorName",
            "mcc": "merchant_category_code",
            "ultimateCreditor": "ultimate_creditor",
        },
    )

    metadata = importer.add_metadata(transaction, {}, config)

    assert "ref" in metadata
    assert metadata["ref"] == "TX123"
    assert "payee" in metadata
    assert metadata["payee"] == "Test Creditor"
    assert "mcc" in metadata
    assert metadata["mcc"] == "5411"
    assert "ultimateCreditor" in metadata
    assert metadata["ultimateCreditor"] == "Store Inc"
    # Note: defaults are also included unless excluded
    assert "debtorName" in metadata
    assert "bookingDate" in metadata


def test_add_metadata_custom_overrides_default(importer):
    """Test that custom metadata overrides default metadata keys."""
    transaction = BankTransaction(
        transaction_id="TX123",
        creditor_name="Test Creditor",
        booking_date="2026-01-15",
        transaction_amount=TransactionAmountSchema(amount="100.00", currency="EUR"),
    )

    config = AccountConfig(id="ACC1", asset_account="Assets:Test")
    custom_meta = {"nordref": "CUSTOM123", "custom": "value"}

    metadata = importer.add_metadata(transaction, custom_meta, config)

    assert metadata["nordref"] == "CUSTOM123"
    assert metadata["custom"] == "value"
    assert metadata["creditorName"] == "Test Creditor"


def test_add_metadata_without_account_config(importer):
    """Test that default metadata is added when no account_config provided."""
    transaction = BankTransaction(
        transaction_id="TX123",
        creditor_name="Test Creditor",
        booking_date="2026-01-15",
        transaction_amount=TransactionAmountSchema(amount="100.00", currency="EUR"),
    )

    metadata = importer.add_metadata(transaction, {}, None)

    # Should include all default fields that have non-None values
    assert metadata["nordref"] == "TX123"
    assert metadata["creditorName"] == "Test Creditor"
    assert metadata["bookingDate"] == "2026-01-15"
    assert "debtorName" not in metadata  # debtorName is None, so excluded


def test_add_metadata_flattens_nested_dicts(importer):
    """Test that nested dicts are flattened to dotted paths via metadata_fields."""

    transaction = BankTransaction(
        transaction_id="TX123",
        transaction_amount=TransactionAmountSchema(amount="100.00", currency="EUR"),
        additional_data_structured={
            "cardInstrument": {
                "cardSchemeName": "MASTERCARD",
                "name": "John Doe",
                "identification": "1234",
            }
        },
        balance_after_transaction=BalanceAfterTransactionSchema(
            balance_amount=BalanceAmountSchema(amount="9.52", currency="EUR"),
            balance_type="InterimBooked",
        ),
    )

    config = AccountConfig(
        id="ACC1",
        asset_account="Assets:Test",
        metadata_fields={
            "additionalDataStructured.cardInstrument.cardSchemeName": "additionalDataStructured.cardInstrument.cardSchemeName",
            "additionalDataStructured.cardInstrument.name": "additionalDataStructured.cardInstrument.name",
            "additionalDataStructured.cardInstrument.identification": "additionalDataStructured.cardInstrument.identification",
            "balanceAfterTransaction.balance_type": "balanceAfterTransaction.balance_type",
            "balanceAfterTransaction.balance_amount.amount": "balanceAfterTransaction.balance_amount.amount",
            "balanceAfterTransaction.balance_amount.currency": "balanceAfterTransaction.balance_amount.currency",
        },
    )

    metadata = importer.add_metadata(transaction, {}, config)

    # Check nested additionalDataStructured is flattened
    assert (
        metadata["additionalDataStructured.cardInstrument.cardSchemeName"]
        == "MASTERCARD"
    )
    assert metadata["additionalDataStructured.cardInstrument.name"] == "John Doe"
    assert metadata["additionalDataStructured.cardInstrument.identification"] == "1234"

    # Check nested balanceAfterTransaction is flattened
    assert metadata["balanceAfterTransaction.balance_type"] == "InterimBooked"
    assert metadata["balanceAfterTransaction.balance_amount.amount"] == "9.52"
    assert metadata["balanceAfterTransaction.balance_amount.currency"] == "EUR"

    # Check default fields are also present
    assert metadata["nordref"] == "TX123"


def test_add_metadata_with_card_transaction_nested(importer):
    """Test that custom fields can directly specify desired output keys."""
    transaction = BankTransaction(
        transaction_id="TX789",
        transaction_amount=TransactionAmountSchema(amount="25.00", currency="EUR"),
        additional_data_structured={
            "cardInstrument": {
                "cardSchemeName": "VISA",
            }
        },
    )

    config = AccountConfig(
        id="ACC1",
        asset_account="Assets:Test",
        metadata_fields={
            "card_scheme": "additionalDataStructured.cardInstrument.cardSchemeName",
        },
    )

    metadata = importer.add_metadata(transaction, {}, config)

    assert metadata["card_scheme"] == "VISA"
    # Check defaults are also present
    assert "nordref" in metadata


def test_add_metadata_nested_with_exclude(importer):
    """Test that specific nested keys can be excluded."""
    transaction = BankTransaction(
        transaction_id="TX999",
        transaction_amount=TransactionAmountSchema(amount="75.00", currency="EUR"),
        additional_data_structured={
            "cardInstrument": {
                "cardSchemeName": "AMEX",
                "name": "Jane Doe",
            }
        },
    )

    config = AccountConfig(
        id="ACC1",
        asset_account="Assets:Test",
        metadata_fields={
            "additionalDataStructured.cardInstrument.cardSchemeName": "additionalDataStructured.cardInstrument.cardSchemeName",
            "additionalDataStructured.cardInstrument.name": "additionalDataStructured.cardInstrument.name",
        },
        exclude_default_metadata=["additionalDataStructured.cardInstrument.name"],
    )

    metadata = importer.add_metadata(transaction, {}, config)

    assert metadata["additionalDataStructured.cardInstrument.cardSchemeName"] == "AMEX"
    assert "additionalDataStructured.cardInstrument.name" not in metadata
