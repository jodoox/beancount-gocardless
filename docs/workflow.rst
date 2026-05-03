Workflow
========

Recommended flow
----------------

For most setups the shortest path is:

1. Create a provider config file.
2. Keep credentials in ``.env`` or explicit ``env_files`` entries.
3. Use the CLI to authorize the provider connection.
4. List accounts and copy the provider account IDs into the config.
5. Run the importer through your ``beangulp`` script.

GoCardless
----------

.. code-block:: bash

    beancount-gocardless --config gocardless.yaml
    beancount-openbanking gocardless --config gocardless.yaml accounts
    python my_import.py extract ./gocardless.yaml --existing ./ledger.bean

Enable Banking
--------------

Enable Banking sessions are stored as individual JSON files in a directory
(``session_store_path``), so multiple bank authorizations can coexist.

.. code-block:: bash

    beancount-enablebanking --config enablebanking.yaml
    beancount-openbanking enablebanking --config enablebanking.yaml accounts
    python my_import.py extract ./enablebanking.yaml --existing ./ledger.bean

Provider-specific CLIs infer the provider type from the command being used, so
legacy single-provider GoCardless configs without an explicit ``provider``
field still work there. For new configs, keeping the field explicit is
recommended.
