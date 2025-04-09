.. beancount-gocardless documentation master file, created by
   sphinx-quickstart on Fri Feb 28 10:26:10 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

beancount-gocardless docs
==================================

.. contents:: Table of Contents
   :depth: 2

Introduction
------------

This package provides a basic client for interacting with the GoCardless API (formerly Nordigen) and importing your data into Beancount.

This project was inspired by the structure and approach used in https://github.com/tarioch/beancounttools/.


**Key Features:**

- **GoCardless API Client:**  A client for interacting with the GoCardless API. The client has built-in caching via :code:`requests-cache`.
- **GoCardLess CLI**\: A command-line interface to manage authorization with the GoCardless API:

    - Listing available banks in a specified country (default: GB).
    - Creating a link to a specific bank using its ID.
    - Listing authorized accounts.
    - Deleting an existing link.
    - Uses environment variables (:code:`NORDIGEN_SECRET_ID`, :code:`NORDIGEN_SECRET_KEY`) or command-line arguments for API credentials.
- **Beancount Importer:**  A :code:`beangulp.Importer` implementation to easily import transactions fetched from the GoCardless API directly into your Beancount ledger.

You'll need to create a GoCardLess account on https://bankaccountdata.gocardless.com/overview/ to get your credentials.

Installation
------------

.. code-block:: bash

    pip install beancount-gocardless

Dependencies
------------

The project requires Python >= 3.12 and has the following dependencies (as specified in `pyproject.toml`):

*   requests
*   requests-cache
*   beancount
*   beangulp
*   pyyaml

API Reference
-------------

.. _cli-api:

CLI Documentation
-----------------

.. include:: cli.rst

.. automodule:: beancount_gocardless.cli
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
