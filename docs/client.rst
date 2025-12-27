GoCardless Client
=================

Auto-generated from swagger.json. Typed with Pydantic. Full caching support. Header stripping. Token refresh. Cache status check.

Features
--------

- Typed responses via Pydantic models
- Convenience methods: list_banks(), create_bank_link(), get_all_accounts()
- All 14 API endpoints
- Error handling with token refresh
- Caching: sqlite, configurable expiry
- Header stripping for privacy
- Cache debugging via check_cache_status()

Usage
-----

.. code-block:: python

    from beancount_gocardless import GoCardlessClient

    client = GoCardlessClient("secret_id", "secret_key", cache_options={
        "cache_name": "my_cache",
        "expire_after": 3600
    })

    banks = client.list_banks("GB")
    accounts = client.get_all_accounts()

CLI
---

.. code-block:: bash

    beancount-gocardless list_banks --country GB --cache --cache_expire 3600
    beancount-gocardless create_link --reference mybank --bank SANDBOXFINANCE_SFIN0000 --cache

Regeneration
------------

Update API: cd openapi; ./regen_simple_client.sh
