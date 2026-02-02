[![PyPI](https://img.shields.io/pypi/v/beancount-gocardless.svg)](https://pypi.org/project/beancount-gocardless/)
[![Python versions](https://img.shields.io/pypi/pyversions/beancount-gocardless.svg)](https://pypi.org/project/beancount-gocardless/)
[![License](https://img.shields.io/pypi/l/beancount-gocardless.svg)](https://pypi.org/project/beancount-gocardless/)
[![Documentation Status](https://readthedocs.org/projects/beancount-gocardless/badge/?version=latest)](https://beancount-gocardless.readthedocs.io/en/latest/)
[![Publish](https://github.com/jodoox/beancount-gocardless/actions/workflows/publish.yml/badge.svg?branch=main)](https://github.com/jodoox/beancount-gocardless/actions/workflows/publish.yml)

# beancount-gocardless

Python client for the GoCardless Bank Account Data API (formerly Nordigen), with Pydantic models recreated from the OpenAPI/Swagger spec, plus a Beancount importer.

Inspired by https://github.com/tarioch/beancounttools.

Documentation: https://beancount-gocardless.readthedocs.io/en/latest/

## Key features

- API client with typed Pydantic models for endpoints and data structures.
- Built-in HTTP caching via `requests-cache` (optional).
- CLI to manage bank authorization (list banks, create links, list accounts, delete links).
- Beancount importer: a `beangulp.Importer` implementation that fetches transactions and emits Beancount entries.
- Import-time metadata control (exclude fields, add custom fields), plus subclassing hooks for advanced needs.

## Installation

```bash
pip install beancount-gocardless
```

## Prerequisites (credentials)

Create a GoCardless Bank Account Data account to get API credentials:

https://bankaccountdata.gocardless.com/overview/

You will need:

- `GOCARDLESS_SECRET_ID`
- `GOCARDLESS_SECRET_KEY`

## CLI usage (bank authorization)

The importer needs an authorized bank connection first. Use the CLI to create and manage connections.

Set credentials as environment variables:

```bash
export GOCARDLESS_SECRET_ID="..."
export GOCARDLESS_SECRET_KEY="..."
```

Launch the CLI:

```bash
beancount-gocardless
```

Options:
- List accounts: view connected accounts with expiry status (EXPIRED badge shown for expired connections), select an account to view details, check balances, or delete the link
- Add account: add a new bank connection by selecting country, choosing a bank, and creating an authorization link
- List banks: browse available banks by country and create links

Account expiry is shown in the list. Use --mock flag for testing without real credentials.

## Beancount usage

### 1) Create a YAML config

Create `gocardless.yaml`:

```yaml
secret_id: $GOCARDLESS_SECRET_ID
secret_key: $GOCARDLESS_SECRET_KEY

# Note: this project substitutes environment variables in YAML values at runtime.

cache_options: # if omitted, caching is disabled
  cache_name: "gocardless"
  backend: "sqlite"
  expire_after: 3600
  old_data_on_error: true

accounts:
  - id: "<REDACTED_UUID>"
    asset_account: "Assets:Banks:Revolut:Checking"
    transaction_types: ["booked", "pending"] # optional, defaults to both
    preferred_balance_type: "interimAvailable" # optional
```

### 2) Create an import script

Create `my.import`:

```python
#!/usr/bin/env python3

import beangulp
from beancount_gocardless import GoCardLessImporter
from smart_importer import PredictPayees, PredictPostings

importers = [
    GoCardLessImporter(),
]

hooks = [
    PredictPostings().hook,
    PredictPayees().hook,
]

if __name__ == "__main__":
    ingest = beangulp.Ingest(importers, hooks=hooks)
    ingest()
```

### 3) Run the import

```bash
python my.import extract ./gocardless.yaml --existing ./ledger.bean
```

## Customizing metadata

### Via YAML configuration

You can control metadata per account:

```yaml
accounts:
  - id: "<REDACTED_UUID>"
    asset_account: "Assets:Banks:Revolut:Checking"

    # Exclude specific default metadata fields.
    exclude_default_metadata: ["bookingDate", "creditorName"]

    # Add custom metadata fields using dotted paths.
    metadata_fields:
      payee: "creditorName"
      cardScheme: "additionalDataStructured.cardInstrument.cardSchemeName"
      balanceType: "balanceAfterTransaction.balance_type"
```

Supported options:

- `exclude_default_metadata` (default: `[]`) - Exclude specific default metadata fields.
  - Default fields include: `nordref`, `creditorName`, `debtorName`, `bookingDate`
- `metadata_fields` (default: `null`) - Add or override metadata fields using dotted paths.
  - Specify the output key as the dict key and the GoCardless path as the value.
  - Example: `"cardScheme": "additionalDataStructured.cardInstrument.cardSchemeName"`

### Example configurations

**Use defaults with exclusions:**

```yaml
accounts:
  - id: "<REDACTED_UUID>"
    asset_account: "Assets:Banks:Revolut:Checking"
    exclude_default_metadata: ["bookingDate"]  # Keep nordref, creditorName, debtorName
```

**Full customization with custom keys:**

```yaml
accounts:
  - id: "<REDACTED_UUID>"
    asset_account: "Assets:Banks:Revolut:Checking"
    exclude_default_metadata: []  # Keep all defaults
    metadata_fields:
      # Rename default field by using custom key name
      payee: "creditorName"
      # Add nested custom fields
      cardScheme: "additionalDataStructured.cardInstrument.cardSchemeName"
      mcc: "merchant_category_code"
      ultimateCreditor: "ultimate_creditor"
```

### Via subclassing

For advanced customization, subclass `GoCardLessImporter` and override `add_metadata`:

```python
from beancount_gocardless import GoCardLessImporter

class CustomImporter(GoCardLessImporter):
    def add_metadata(self, transaction, custom_metadata, account_config=None):
        metakv = super().add_metadata(transaction, custom_metadata, account_config)

        if transaction.ultimate_creditor:
            metakv["ultimateCreditor"] = transaction.ultimate_creditor
        if transaction.merchant_category_code:
            metakv["mcc"] = transaction.merchant_category_code
        if transaction.bank_transaction_code:
            metakv["bankCode"] = transaction.bank_transaction_code

        return metakv

importers = [CustomImporter()]
```

The `BankTransaction` model (see `models.py`) contains many optional fields you can expose as metadata, for example:

- `ultimate_creditor`, `ultimate_debtor`
- `bank_transaction_code`, `proprietary_bank_transaction_code`
- `merchant_category_code`, `creditor_id`, `mandate_id`
- `entry_reference`, `account_servicer_reference`

## Development

### API coverage and models

The GoCardless client aims to provide full API coverage with typed models for endpoints and data structures.

Models are manually recreated from the OpenAPI/Swagger spec to keep strong typing and stable semantics.

### Local development

```bash
git clone https://github.com/jodoox/beancount-gocardless.git
cd beancount-gocardless
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
pytest
```
