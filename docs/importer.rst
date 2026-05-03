Importer
========

``BankImporter`` reads a provider-specific YAML file, fetches transactions and
balances, and emits Beancount directives.

Workflow
--------

The usual flow is:

1. create a provider config file
2. authorize or inspect accounts with the CLI
3. add the provider account IDs to the config
4. run the importer against your Beancount ledger

Configuration
-------------

Each config file must define:

* ``provider``: ``gocardless`` or ``enablebanking``
* ``accounts``: one or more account definitions

The provider-specific CLIs can infer ``provider`` from the selected subcommand,
which keeps older single-provider configs usable. The generic
``BankImporter`` still expects it to be present.

Optional top-level fields:

* ``currency``: fallback currency if a transaction omits one
* ``env_files``: dotenv files resolved relative to the YAML file
* ``env``: inline values used during variable expansion

Variable expansion supports ``$VAR`` and ``${VAR}`` in string values.
Path fields are resolved relative to the YAML file. For Enable Banking this
applies to ``private_key_path`` and ``session_store_path``.

GoCardless example
~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    provider: gocardless
    env_files:
      - .env
    secret_id: $GOCARDLESS_SECRET_ID
    secret_key: $GOCARDLESS_SECRET_KEY

    accounts:
      - id: "ACCOUNT_ID"
        asset_account: "Assets:Banks:Checking"
        booking_statuses: ["booked", "pending"]
        preferred_balance_type: "interimAvailable"

Enable Banking example
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

    provider: enablebanking
    env_files:
      - .env
    application_id: $ENABLE_BANKING_APPLICATION_ID
    private_key_path: $ENABLE_BANKING_PRIVATE_KEY_PATH
    redirect_url: "http://127.0.0.1:8765/callback"
    session_store_path: ".secrets/enablebanking-sessions"

    accounts:
      - id: "ACCOUNT_UID"
        asset_account: "Assets:Banks:Checking"
        booking_statuses: ["booked", "pending"]
        preferred_balance_type: "CLOSING"

Per-account fields
------------------

* ``id``: provider account identifier
* ``asset_account``: target Beancount account
* ``metadata``: static metadata added to emitted directives
* ``booking_statuses``: ``booked`` and/or ``pending``
* ``preferred_balance_type``: preferred balance when several are returned
* ``exclude_default_metadata``: remove default metadata keys
* ``metadata_fields``: map output metadata keys to provider field paths
* ``days_back``: lookback window for transactions

For Enable Banking, ``session_store_path`` is a directory rather than a single
JSON file. Each authorized session is stored as a separate JSON document inside
that directory.

Default metadata keys
---------------------

* ``ref``
* ``creditorName``
* ``debtorName``
* ``bookingDate``

Usage
-----

Minimal ``beangulp`` script:

.. code-block:: python

    import beangulp
    from beancount_openbanking import BankImporter

    if __name__ == "__main__":
        ingest = beangulp.Ingest([BankImporter()])
        ingest()

Run it:

.. code-block:: bash

    python my_import.py extract ./gocardless.yaml --existing ./ledger.bean
    python my_import.py extract ./enablebanking.yaml --existing ./ledger.bean

Reference
---------

.. automodule:: beancount_openbanking.importer
   :members:
   :undoc-members:
   :show-inheritance:
