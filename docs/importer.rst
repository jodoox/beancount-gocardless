Nordigen Importer for Beancount
=================================

This module provides an importer for Nordigen API transactions to be used with Beancount
It handles fetching data from the API, parsing transactions, and generating Beancount entries.  It is designed to
be extensible, allowing for customization of metadata extraction, narration, payee, date, transaction status and
entry creation.

Classes
-------

-   ``NordigenImporter``: The main importer class responsible for interacting with the Nordigen API and generating Beancount entries.

Configuration
-------------

The importer is configured through a YAML file.  See the example configuration files for more details. The key configurations are:

-   ``secret_id``: Your Nordigen API secret ID.
-   ``secret_key``: Your Nordigen API secret key.
-   ``cache_options``: (Optional) Options for configuring the API response caching. This uses the `requests-cache` library.

    -  ``cache_name``: (Optional) The name of the cache. Defaults to "nordigen".
    -  ``backend``: (Optional) The caching backend to use. Defaults to "sqlite". Other options include "memory", "redis", "mongodb", and "filesystem". See the `requests-cache` documentation for details.
    -  ``expire_after``: (Optional) The cache expiration time in seconds. Defaults to 86400 (24 hours). Set to -1 to never expire.
    -  ``old_data_on_error``: (Optional) If True and there is an API error, returns old cached data. Defaults to True.

- ``accounts``: A list of account configurations. Each account configuration should include:

    -   ``id``: The Nordigen account ID.
    -   ``asset_account``: The Beancount asset account to post transactions to.
    -   ``filing_account``: (Optional) A Beancount account for additional metadata (e.g., a linked account).  This will be set as metadata on all the imported transactions and can then be read by other hooks (see `redstreet's patch to beangulp extract`).


Usage
-----

1.  Create a YAML configuration file with your Nordigen API credentials and account details. Environment variables are automatically expanded when loading the file.
2.  Use ``beangulp`` or your preferred method to load and run the importer, passing the configuration file as input.

Example
-------
.. code-block:: yaml
    :caption: nordigen.yaml

    secret_id: $NORDIGEN_SECRET_ID
    secret_key: $NORDIGEN_SECRET_KEY

    cache_options: # by default, no caching if cache_options is not provided
        cache_name: "nordigen"
        backend: "sqlite"
        expire_after: 3600
        old_data_on_error: false

    accounts:
        - id: <REDACTED_UUID>
        asset_account: "Assets:Banks:Revolut:Checking"

.. code-block:: python
    :caption: my.import

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

.. code-block:: bash
    :caption: Run the importer

    python my.import extract ./nordigen.yaml --existing ./ledger.bean


Extensibility
-------------

The ``NordigenImporter`` class is designed for extensibility.  Key methods can be overridden in a subclass to customize the importer's behavior:

-   ``add_metadata(self, transaction, filing_account)``:  Extracts and formats metadata from a transaction.  Override this to add or modify metadata fields.
-   ``get_narration(self, transaction)``:  Extracts the narration from a transaction.  Override this to customize the narration format.
-   ``get_payee(self, transaction)``: Extracts the payee from a transaction. Override to customize.
-   ``get_transaction_date(self, transaction)``: Extracts the transaction date. Override to handle date formats differently.
-   ``get_transaction_status(self, status)``:  Determines the Beancount transaction flag (e.g., ``*`` or ``!``). Override to use different flags based on transaction status.
-   ``create_transaction_entry(self, transaction, status, asset_account, filing_account)``:  Creates the complete Beancount transaction entry.  Override this for full control over entry creation.
