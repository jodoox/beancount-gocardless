GoCardless CLI
===============

Commands: list banks, create/delete links, list accounts, check balances. Uses GoCardlessClient. Args or env vars.

Usage
-----

.. code-block:: console

    beancount-gocardless <mode> [options]

Modes
-----

- list_banks: Banks by country
- create_link: Create bank link
- list_accounts: Connected accounts
- delete_link: Delete link
- balance: Account balance

Options
-------

- --secret_id: Secret ID (env: GOCARDLESS_SECRET_ID)
- --secret_key: Secret key (env: GOCARDLESS_SECRET_KEY)
- --country: Country code, default "GB" (list_banks)
- --reference: Reference, default "beancount" (create_link/delete_link)
- --bank: Bank ID (create_link)
- --account: Account ID (balance)
- --cache: Enable caching
- --cache_backend: Backend, default "sqlite"
- --cache_expire: Expiry secs, default 0
- --cache_name: Name, default "gocardless"

Examples
--------

- List UK banks: beancount-gocardless list_banks --country GB
- Create link: beancount-gocardless create_link --bank MY_BANK_ID --reference myref
- List accounts: beancount-gocardless list_accounts
- Delete link: beancount-gocardless delete_link --reference myref
- Check balance: beancount-gocardless balance --account MY_ACCOUNT_ID
