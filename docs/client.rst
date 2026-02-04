API Client
==========

The `GoCardlessClient` provides a typed interface to the GoCardless Bank Account Data API.

Features
--------

*   **Typed Models**: Requests and responses use Pydantic models.
*   **Caching**: Cache API responses via `requests-cache`.
*   **Token Management**: Handles access token acquisition and refreshing.
*   **Privacy**: Strips sensitive headers from logs.

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
