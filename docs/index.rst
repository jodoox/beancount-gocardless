beancount-gocardless
====================

A Python client for the GoCardless Bank Account Data API (formerly Nordigen), featuring Pydantic models and a Beancount importer.

.. image:: https://img.shields.io/pypi/v/beancount-gocardless.svg
   :target: https://pypi.org/project/beancount-gocardless/
   :alt: PyPI

.. image:: https://img.shields.io/pypi/pyversions/beancount-gocardless.svg?v=1
   :target: https://pypi.org/project/beancount-gocardless/
   :alt: Python versions

.. image:: https://img.shields.io/pypi/l/beancount-gocardless.svg
   :target: https://pypi.org/project/beancount-gocardless/
   :alt: License

Overview
--------

`beancount-gocardless` provides an integration between the GoCardless Bank Account Data API and Beancount. It includes:

*   **API Client**: Typed client using Pydantic models for endpoints and data structures.
*   **CLI Tool**: Interactive interface to manage bank connections.
*   **Beancount Importer**: A `beangulp` importer that fetches transactions and converts them into Beancount directives.

Prerequisites
-------------

You need a GoCardless Bank Account Data account to obtain your API credentials (`secret_id` and `secret_key`).
Sign up at `GoCardless Bank Account Data <https://bankaccountdata.gocardless.com/overview/>`_.

Installation
------------

.. code-block:: bash

    pip install beancount-gocardless

The project requires Python 3.12+.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   client
   cli
   importer
