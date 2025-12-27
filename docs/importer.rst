GoCardless Importer
==================

Imports GoCardless API transactions to Beancount. Fetches data, parses, generates entries. Extensible.

Classes
-------

- GoCardLessImporter: Main importer class.

Config
------

YAML file:

- secret_id, secret_key: API creds
- cache_options (opt): Caching
  - cache_name (opt): Name, default "gocardless"
  - backend (opt): Type, default "sqlite"
  - expire_after (opt): Secs, default 0
  - old_data_on_error (opt): Use cache on error, default True
- accounts: List
  - id: Account ID
  - asset_account: Beancount asset account
  - filing_account (opt): For hooks

Usage
-----

1. YAML config with creds/accounts.
2. Run via beangulp or script.

Example
-------
.. code-block:: yaml

    secret_id: $GOCARDLESS_SECRET_ID
    secret_key: $GOCARDLESS_SECRET_KEY
    cache_options:
        cache_name: "gocardless"
        backend: "sqlite"
        expire_after: 3600
        old_data_on_error: true
    accounts:
        - id: <REDACTED_UUID>
          asset_account: "Assets:Banks:Revolut:Checking"

.. code-block:: python

    import beangulp
    from beancount_gocardless import GoCardLessImporter
    from smart_importer import apply_hooks, PredictPostings, PredictPayees

    importers = [apply_hooks(GoCardLessImporter(), [PredictPostings(), PredictPayees()])]

    if __name__ == "__main__":
        ingest = beangulp.Ingest(importers)
        ingest()

.. code-block:: bash

    python my.import extract ./gocardless.yaml --existing ./ledger.bean

Extensibility
-------------

Override methods:

- add_metadata(): Add metadata
- get_narration(): Customize narration
- get_payee(): Customize payee
- get_transaction_date(): Handle dates
- get_transaction_status(): Set flags
- create_transaction_entry(): Full control

CLI
---

Manage connections:

.. code-block:: bash

    beancount-gocardless list_banks --country GB
    beancount-gocardless create_link --bank SANDBOXFINANCE_SFIN0000 --reference myaccount
    beancount-gocardless list_accounts
    beancount-gocardless balance --account <ACCOUNT_ID>

Use beancount-gocardless --help for options.
