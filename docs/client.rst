Providers
=========

Provider implementations live under ``beancount_openbanking.providers`` and
normalize external APIs into a common account, balance, and transaction model.

Available providers:

* ``GoCardlessProvider``
* ``EnableBankingProvider``

Shared protocol
---------------

Each provider implements:

* ``ensure_session()``
* ``list_accounts()``
* ``get_balances(account_id)``
* ``get_transactions(account_id, booked_from=None, booked_to=None)``

GoCardless also exposes institution, requisition, and deletion helpers used by
the CLI. Enable Banking also exposes bank listing, interactive authorization,
session deletion, and multi-session helpers.

Example
-------

.. code-block:: python

    from beancount_openbanking import GoCardlessProvider

    provider = GoCardlessProvider(
        secret_id="your-secret-id",
        secret_key="your-secret-key",
    )

    accounts = provider.list_accounts()
    balances = provider.get_balances("account-id")
    transactions = provider.get_transactions("account-id")

Reference
---------

.. automodule:: beancount_openbanking.providers.base
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: beancount_openbanking.providers.gocardless
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: beancount_openbanking.providers.enablebanking
   :members:
   :undoc-members:
   :show-inheritance:
