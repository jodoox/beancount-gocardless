import pytest
from beancount_gocardless.models import AccountTransactions


@pytest.fixture
def complex_transaction_payload():
    """Complex multi-currency transaction with nested structures."""
    return {
        "transactions": {
            "booked": [
                {
                    "transactionId": "uuid",
                    "bookingDate": "2026-01-05",
                    "valueDate": "2026-01-06",
                    "bookingDateTime": "2026-01-05T12:12:09.133455Z",
                    "valueDateTime": "2026-01-06T02:47:00.1234324Z",
                    "transactionAmount": {"amount": "-4.07", "currency": "EUR"},
                    "currencyExchange": {
                        "instructedAmount": {"amount": "4.07", "currency": "EUR"},
                        "sourceCurrency": "EUR",
                        "exchangeRate": "1.15",
                        "unitCurrency": "EUR",
                        "targetCurrency": "USD",
                    },
                    "creditorName": "Dunkin Donuts",
                    "remittanceInformationUnstructuredArray": ["Dunkin Donuts"],
                    "proprietaryBankTransactionCode": "CARD_PAYMENT",
                    "balanceAfterTransaction": {
                        "balanceAmount": {"amount": "9.52", "currency": "EUR"},
                        "balanceType": "InterimBooked",
                    },
                    "additionalDataStructured": {
                        "cardInstrument": {
                            "cardSchemeName": "MASTERCARD",
                            "name": "John Doe",
                            "identification": "1234",
                        }
                    },
                    "internalTransactionId": "85ecaab0e28caccd799bb8b331285ba5",
                }
            ],
            "pending": [],
        }
    }


@pytest.fixture
def complex_transaction_model(complex_transaction_payload):
    """AccountTransactions model loaded from the complex payload."""
    return AccountTransactions(**complex_transaction_payload)
