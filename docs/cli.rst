CLI Tool
========

The ``beancount-gocardless`` CLI is an interactive tool for managing bank connections.

Usage
-----

To start the interactive CLI:

.. code-block:: bash

    beancount-gocardless

Configuration
-------------

The CLI requires your GoCardless API credentials. You can provide them via environment variables (recommended) or command-line arguments.

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    export GOCARDLESS_SECRET_ID="your-secret-id"
    export GOCARDLESS_SECRET_KEY="your-secret-key"

Command-Line Arguments
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: console

    $ beancount-gocardless --help
    usage: beancount-gocardless [-h] [--secret-id SECRET_ID] [--secret-key SECRET_KEY] [--mock] [--env-file ENV_FILE]

    Interactive CLI for GoCardless Bank Account Data

    options:
      -h, --help            show this help message and exit
      --secret-id SECRET_ID
                            API secret ID (defaults to env var GOCARDLESS_SECRET_ID)
      --secret-key SECRET_KEY
                            API secret key (defaults to env var GOCARDLESS_SECRET_KEY)
      --mock                Use mock client with fixture data (for testing)
      --env-file ENV_FILE   Path to a .env file to load environment variables from

Interactive Features
--------------------

Once launched, the CLI provides the following features through an interactive menu:

*   **List accounts**: View all connected bank accounts, their status (valid/expired), and IBANs.
*   **Add account**: Connect a new bank account by selecting your country and bank, then generating an authorization link.
*   **List banks**: Browse available banks in supported countries.
*   **View balance**: Check the current balance of any connected account.
*   **Delete link**: Remove a bank connection.
*   **Renew connection**: Re-authorize an expired bank connection.

Mock Mode
---------

You can explore the CLI without real credentials using the ``--mock`` flag:

.. code-block:: bash

    beancount-gocardless --mock

This mode uses local fixture data to simulate API responses.
