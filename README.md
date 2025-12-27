beancount-gocardless
====================

GoCardless API client with models manually recreated from swagger spec, plus Beancount importer.

Inspired by https://github.com/tarioch/beancounttools.

Full documentation at https://beancount-gocardless.readthedocs.io/en/latest/.

**Key Features:**

- **API Client:** Models based on swagger spec. Built-in caching via `requests-cache`.
- **GoCardLess CLI**\: A command-line interface to manage authorization with the GoCardless API:

    - Listing available banks in a specified country (default: GB).
    - Creating a link to a specific bank using its ID.
    - Listing authorized accounts.
    - Deleting an existing link.
    - Uses environment variables (`GOCARDLESS_SECRET_ID`, `GOCARDLESS_SECRET_KEY`) or command-line arguments for API credentials.
- **Beancount Importer:**  A `beangulp.Importer` implementation to easily import transactions fetched from the GoCardless API directly into your Beancount ledger.

You'll need to create a GoCardLess account on https://bankaccountdata.gocardless.com/overview/ to get your credentials.

## Development

### API Coverage

The GoCardless client provides **complete API coverage** with Pydantic models for all endpoints and data structures:

**🏦 Core Banking:**
- **Accounts**: Full account metadata, balances, details, and transactions
- **Institutions**: Bank/institution information and capabilities
- **Requisitions**: Bank link management with full lifecycle support

**📋 Agreements & Permissions:**
- **End User Agreements**: Complete agreement lifecycle management
- **Access Scopes**: Granular permission control
- **Reconfirmations**: Agreement renewal workflows

**🔧 Advanced Features:**
- **Integrations**: Institution capability discovery
- **Token Management**: JWT token handling (internal)
- **Pagination**: Full paginated response support
- **Error Handling**: Error response models

**📊 Rich Data Models:**
- **Transactions**: Complete transaction details with currency exchange, balances, and metadata
- **Balances**: Multi-currency balance information with transaction impact
- **Account Details**: Extensive account information including ownership and addresses

Models manually recreated from the swagger spec, providing type-safe access to every API feature.

**Installation:**

```bash
pip install beancount-gocardless
```

**Usage**
```yaml
#### gocardless.yaml
secret_id: $GOCARDLESS_SECRET_ID
secret_key: $GOCARDLESS_SECRET_KEY

cache_options: # by default, no caching if cache_options is not provided
  cache_name: "gocardless"
  backend: "sqlite"
  expire_after: 3600
  old_data_on_error: true

accounts:
    - id: <REDACTED_UUID>
      asset_account: "Assets:Banks:Revolut:Checking"
      transaction_types: ["booked", "pending"]  # optional, defaults to both
```

```python
#### my.import
#!/usr/bin/env python

import beangulp
from beancount_gocardless import GoCardLessImporter
from smart_importer import apply_hooks, PredictPostings, PredictPayees

importers = [
    apply_hooks(
        GoCardLessImporter(),
        [
            PredictPostings(),
            PredictPayees(),
        ],
    )
]

if __name__ == "__main__":
    ingest = beangulp.Ingest(importers)
    ingest()
```

Import your data from GoCardLess's API
```bash
python my.import extract ./gocardless.yaml --existing ./ledger.bean
```
