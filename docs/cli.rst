Command-line interface (CLI) utility for interacting with the Nordigen API.
===============================================================================

This module provides a set of commands to perform common tasks with the Nordigen
API, such as listing available banks, creating and deleting requisition links,
and listing connected accounts. It leverages the ``NordigenClient`` class for
API interactions.  It can either be used via command line argument, or
environment variables.

Functions
---------

*   **parse_args()**: Parses command-line arguments.
*   **main()**: The main entry point for the CLI.

Usage
-----

.. code-block:: console

    python -m beancount_gocardless.cli <mode> [options]

Available modes
---------------

*   **list_banks**: Lists banks available in a specified country.
*   **create_link**: Creates a requisition link for a specific bank.
*   **list_accounts**: Lists connected accounts.
*   **delete_link**: Deletes a requisition link.

Options
-------

*   **--secret_id**: Your Nordigen API secret ID. Defaults to the ``NORDIGEN_SECRET_ID`` environment variable.
*   **--secret_key**: Your Nordigen API secret key. Defaults to the ``NORDIGEN_SECRET_KEY`` environment variable.
*   **--country**: (For ``list_banks``) The two-letter country code (e.g., "GB"). Defaults to "GB".
*   **--reference**: (For ``create_link`` and ``delete_link``) A unique reference string for the requisition. Defaults to "beancount".
*   **--bank**: (For ``create_link``) The ID of the bank to link.

Examples
--------

*   List banks in the UK:

    .. code-block:: console

        python -m beancount_gocardless.cli list_banks --country GB

*   Create a link for a bank with ID 'MY_BANK_ID':

    .. code-block:: console

        python -m beancount_gocardless.cli create_link --bank MY_BANK_ID --reference myref

*   List all connected accounts:

    .. code-block:: console

        python -m beancount_gocardless.cli list_accounts

*   Delete a link with reference 'myref':

    .. code-block:: console

        python -m beancount_gocardless.cli delete_link --reference myref
