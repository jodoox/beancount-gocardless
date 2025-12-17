beancount-gocardless docs
=========================

.. contents:: Table of Contents
   :depth: 2

Intro
-----

GoCardless API client with Pydantic models from swagger spec, plus Beancount importer.

Inspired by https://github.com/tarioch/beancounttools/.

Features:

- API Client: Typed models, caching via requests-cache
- CLI: List banks, create/delete links, list accounts, balances. Env vars or args.
- Importer: beangulp.Importer for transactions to Beancount.

Need GoCardless account at https://bankaccountdata.gocardless.com/overview/ for creds.

Install
-------

.. code-block:: bash

    pip install beancount-gocardless

Deps
----

Python >= 3.12. Deps from pyproject.toml: requests, requests-cache, beancount, beangulp, pyyaml.

API Ref
-------

Client
------

.. include:: client.rst

.. automodule:: beancount_gocardless.client
   :members:
   :undoc-members:
   :show-inheritance:

CLI
---

.. include:: cli.rst

.. automodule:: beancount_gocardless.cli
   :members:
   :undoc-members:
   :show-inheritance:

Importer
--------

.. include:: importer.rst

.. automodule:: beancount_gocardless.importer
   :members:
   :undoc-members:
   :show-inheritance:

.. _importer-api:

Importer Documentation
----------------------

.. include:: importer.rst

.. automodule:: beancount_gocardless.importer
   :members:
   :undoc-members:
   :show-inheritance:
