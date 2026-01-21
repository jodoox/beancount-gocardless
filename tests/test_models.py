from beancount_gocardless.models import (
    AccountTransactions,
    BankTransaction,
    TransactionSchema,
)


def test_currency_exchange_normalization_dict():
    """Test that a dictionary in currency_exchange is normalized to a list."""
    test_data = {
        "transactions": {
            "booked": [
                {
                    "transaction_id": "tx1",
                    "transaction_amount": {"amount": "-50.00", "currency": "GBP"},
                    "currency_exchange": {
                        "source_currency": "GBP",
                        "exchange_rate": "1.0",
                    },
                }
            ],
            "pending": [],
        }
    }

    # Test AccountTransactions
    model = AccountTransactions(**test_data)
    booked_tx = model.transactions["booked"][0]
    assert isinstance(booked_tx.currency_exchange, list)
    assert len(booked_tx.currency_exchange) == 1
    assert booked_tx.currency_exchange[0].source_currency == "GBP"


def test_currency_exchange_normalization_with_aliases():
    """Test normalization using camelCase aliases (user provided example)."""
    test_data = {
        "transactions": {
            "booked": [
                {
                    "transactionId": "tx1",
                    "transactionAmount": {"amount": "-50.00", "currency": "GBP"},
                    "currencyExchange": {
                        "sourceCurrency": "GBP",
                        "exchangeRate": "1.0",
                    },
                }
            ],
            "pending": [],
        }
    }

    model = AccountTransactions(**test_data)
    booked_tx = model.transactions["booked"][0]
    assert isinstance(booked_tx.currency_exchange, list)
    assert len(booked_tx.currency_exchange) == 1
    assert booked_tx.currency_exchange[0].source_currency == "GBP"


def test_currency_exchange_none():
    """Test that None in currency_exchange remains None."""
    test_data = {
        "transaction_id": "tx1",
        "transaction_amount": {"amount": "-50.00", "currency": "GBP"},
        "currency_exchange": None,
    }

    model = BankTransaction(**test_data)
    assert model.currency_exchange is None


def test_currency_exchange_list():
    """Test that a list in currency_exchange remains a list."""
    test_data = {
        "transaction_id": "tx1",
        "transaction_amount": {"amount": "-50.00", "currency": "GBP"},
        "currency_exchange": [{"source_currency": "GBP", "exchange_rate": "1.0"}],
    }

    model = BankTransaction(**test_data)
    assert isinstance(model.currency_exchange, list)
    assert len(model.currency_exchange) == 1
    assert model.currency_exchange[0].source_currency == "GBP"


def test_transaction_schema_normalization():
    """Test normalization in TransactionSchema."""
    test_data = {
        "transaction_id": "tx1",
        "transaction_amount": {"amount": "-50.00", "currency": "GBP"},
        "currency_exchange": {"source_currency": "GBP", "exchange_rate": "1.0"},
    }

    model = TransactionSchema(**test_data)
    assert isinstance(model.currency_exchange, list)
    assert len(model.currency_exchange) == 1


def test_complex_multi_currency_normalization(complex_transaction_model):
    """Test normalization with the user's complex multi-currency JSON sample."""
    booked_tx = complex_transaction_model.transactions["booked"][0]

    assert isinstance(booked_tx.currency_exchange, list)
    assert len(booked_tx.currency_exchange) == 1
    assert booked_tx.currency_exchange[0].source_currency == "EUR"
    assert booked_tx.currency_exchange[0].instructed_amount.amount == "4.07"
    assert booked_tx.currency_exchange[0].target_currency == "USD"


def test_additional_data_structured_is_dict(complex_transaction_model):
    """Test that additionalDataStructured is stored as a dict (not string)."""
    booked_tx = complex_transaction_model.transactions["booked"][0]

    assert isinstance(booked_tx.additional_data_structured, dict)
    assert "cardInstrument" in booked_tx.additional_data_structured
    assert (
        booked_tx.additional_data_structured["cardInstrument"]["cardSchemeName"]
        == "MASTERCARD"
    )


def test_balance_after_transaction_is_model(complex_transaction_model):
    """Test that balanceAfterTransaction is parsed as a model."""
    booked_tx = complex_transaction_model.transactions["booked"][0]

    assert booked_tx.balance_after_transaction is not None
    assert booked_tx.balance_after_transaction.balance_type == "InterimBooked"
    assert booked_tx.balance_after_transaction.balance_amount.amount == "9.52"
    assert booked_tx.balance_after_transaction.balance_amount.currency == "EUR"
