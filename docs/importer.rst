Beancount Importer
==================

The `GoCardLessImporter` class is a `beangulp.Importer` implementation that fetches transactions from the GoCardless API and converts them into Beancount directives.

Configuration
-------------

The importer is configured using a YAML file. This file contains your credentials, cache settings, and account mappings.

.. code-block:: yaml

    # Credential injection (supported via environment variables)
    secret_id: $GOCARDLESS_SECRET_ID
    secret_key: $GOCARDLESS_SECRET_KEY

    # Optional caching configuration
    cache_options:
      cache_name: "gocardless"   # Default: "gocardless"
      backend: "sqlite"          # Default: "sqlite"
      expire_after: 3600         # Default: 0 (no cache)
      old_data_on_error: true    # Default: true

    # Account configuration
    accounts:
      - id: "ACCOUNT_UUID_FROM_CLI"
        asset_account: "Assets:Bank:MyAccount"

        # Optional settings
        transaction_types: ["booked", "pending"]  # Default: ["booked", "pending"]
        preferred_balance_type: "interimAvailable" # Default: checks expected, closingBooked, etc.

        # Metadata customization
        exclude_default_metadata: ["bookingDate"]
        metadata_fields:
            payee: "creditorName"
            cardScheme: "additionalDataStructured.cardInstrument.cardSchemeName"

Configuration Options
~~~~~~~~~~~~~~~~~~~~~

**Global Settings:**

*   **secret_id**: Your GoCardless Secret ID.
*   **secret_key**: Your GoCardless Secret Key.
*   **cache_options**: Dictionary of settings for `requests-cache`.

**Account Settings:**

*   **id**: The GoCardless Account ID (UUID). Retrieve this using the CLI (`beancount-gocardless list_accounts`).
*   **asset_account**: The Beancount account name to associate with these transactions (e.g., `Assets:Banks:Checking`).
*   **transaction_types**: List of transaction statuses to import. Options: ``booked``, ``pending``.
*   **preferred_balance_type**: The balance type to use for balance assertions. Common values: ``expected``, ``interimAvailable``, ``closingBooked``.
*   **exclude_default_metadata**: List of default metadata keys to exclude (e.g., ``nordref``, ``creditorName``).
*   **metadata_fields**: Dictionary mapping custom metadata keys to fields in the GoCardless API response (supports dotted paths).

Usage
-----

Create a Python script to run the import. This is standard for `beangulp` importers.

**Basic Usage:**

.. code-block:: python

    import beangulp
    from beancount_gocardless import GoCardLessImporter

    importer = GoCardLessImporter()

    if __name__ == "__main__":
        ingest = beangulp.Ingest([importer])
        ingest()

**With Smart Importer (Recommended):**

If you use `smart_importer` to predict payees and accounts:

.. code-block:: python

    import beangulp
    from beancount_gocardless import GoCardLessImporter
    from smart_importer import PredictPostings, PredictPayees

    importer = GoCardLessImporter()

    hooks = [
        PredictPostings().hook,
        PredictPayees().hook,
    ]

    if __name__ == "__main__":
        ingest = beangulp.Ingest([importer], hooks=hooks)
        ingest()

**Running the Import:**

.. code-block:: bash

    python my_import.py extract config.yaml

Extensibility
-------------

You can subclass `GoCardLessImporter` to customize behavior by overriding the following methods:

*   **get_payee(transaction)**: Return the payee string.
*   **get_narration(transaction)**: Return the narration string.
*   **get_transaction_date(transaction)**: Return the transaction date.
*   **add_metadata(transaction, ...)**: Return a dictionary of metadata.
*   **create_transaction_entry(...)**: Complete control over entry creation.

Reference
---------

.. automodule:: beancount_gocardless.importer
   :members:
   :undoc-members:
   :show-inheritance:
