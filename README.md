beancount-gocardless
====================

This package provides a basic client for interacting with the GoCardless API (formerly Nordigen) and importing your data into Beancount.

This project was inspired by https://github.com/tarioch/beancounttools

Full documentation available at https://beancount-gocardless.readthedocs.io/en/latest/


**Key Features:**

- **GoCardless API Client:**  A client for interacting with the GoCardless API. The client has built-in caching via `requests-cache`.
- **GoCardLess CLI**\: A command-line interface to manage authorization with the GoCardless API:

    - Listing available banks in a specified country (default: GB).
    - Creating a link to a specific bank using its ID.
    - Listing authorized accounts.
    - Deleting an existing link.
    - Uses environment variables (`NORDIGEN_SECRET_ID`, `NORDIGEN_SECRET_KEY`) or command-line arguments for API credentials.
- **Beancount Importer:**  A `beangulp.Importer` implementation to easily import transactions fetched from the GoCardless API directly into your Beancount ledger.

You'll need to create a GoCardLess account on https://bankaccountdata.gocardless.com/overview/ to get your credentials.

**Installation:**

```bash
pip install beancount-gocardless
```

**Usage**
```yaml
#### nordigen.yaml
secret_id: $NORDIGEN_SECRET_ID
secret_key: $NORDIGEN_SECRET_KEY

cache_options: # by default, no caching if cache_options is not provided
  cache_name: "nordigen"
  backend: "sqlite"
  expire_after: 3600
  old_data_on_error: true

accounts:
    - id: <REDACTED_UUID>
    asset_account: "Assets:Banks:Revolut:Checking"
```

```python
#### my.import
#!/usr/bin/env python

import beangulp
from beancount_gocardless import NordigenImporter
from smart_importer import apply_hooks, PredictPostings, PredictPayees

importers = [
    apply_hooks(
        NordigenImporter(),
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

Import your data from Nordigen's API
```bash
python my.import extract ./nordigen.yaml --existing ./ledger.bean
```
