API Client
==========

The ``GoCardlessClient`` provides a typed interface to the GoCardless Bank Account Data API.

Features
--------

*   Requests and responses use Pydantic models for type safety.
*   API responses can be cached locally via ``requests-cache`` (SQLite backend by default).
*   Access tokens are acquired and refreshed automatically.
*   Response headers (e.g. ``Cache-Control``) are stripped to prevent them from overriding ``requests-cache`` behavior, which would cause unnecessary re-fetching of cached data.

Usage
-----

Initialize the client with your credentials:

.. code-block:: python

    from beancount_gocardless import GoCardlessClient

    client = GoCardlessClient(
        secret_id="your-secret-id",
        secret_key="your-secret-key",
        cache_options={
            "cache_name": "gocardless_cache",
            "expire_after": 3600  # 1 hour
        }
    )

    # List banks in Great Britain
    banks = client.list_banks("GB")

    # Get all connected accounts
    accounts = client.get_all_accounts()

Reference
---------

.. automodule:: beancount_gocardless.client
   :members:
   :undoc-members:
   :show-inheritance:
