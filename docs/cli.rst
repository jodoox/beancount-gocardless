CLI
===

``beancount-openbanking`` is the primary multi-provider CLI for bank link creation
and provider inspection.

``beancount-gocardless`` is a dedicated GoCardless helper CLI. If you run it
without a subcommand in a TTY, it opens a small ``questionary``-based menu.

``beancount-enablebanking`` is a dedicated Enable Banking helper CLI with the same
interactive menu pattern.

Provider-specific configs loaded through the dedicated helper CLIs infer the
provider name automatically, which keeps legacy one-provider YAML files usable.

GoCardless
----------

List banks:

.. code-block:: bash

    beancount-openbanking gocardless --config gocardless.yaml banks --country FR --search bnp

List requisitions:

.. code-block:: bash

    beancount-openbanking gocardless --config gocardless.yaml links

Create a bank link:

.. code-block:: bash

    beancount-openbanking gocardless --config gocardless.yaml create-link \
      --institution-id REVOLUT_REVOGB21 \
      --reference revolut-main

Delete a bank link:

.. code-block:: bash

    beancount-openbanking gocardless --config gocardless.yaml delete-link \
      --requisition-id <REQUISITION_ID>

Dedicated GoCardless helper:

.. code-block:: bash

    beancount-gocardless --config gocardless.yaml
    beancount-gocardless links
    beancount-gocardless delete-link --requisition-id <REQUISITION_ID>

Enable Banking
--------------

List banks:

.. code-block:: bash

    beancount-openbanking enablebanking --config enablebanking.yaml banks --country FR

Create a bank link and persist the session:

.. code-block:: bash

    beancount-openbanking enablebanking --config enablebanking.yaml create-link \
      --country FR \
      --aspsp-name "BNP Paribas"

``session_store_path`` must point to a directory where per-session JSON files
can be written.

Delete a bank link:

.. code-block:: bash

    beancount-openbanking enablebanking --config enablebanking.yaml delete-link \
      --session-id <SESSION_ID>

List accounts from stored sessions:

.. code-block:: bash

    beancount-openbanking enablebanking --config enablebanking.yaml accounts

Dedicated Enable Banking helper:

.. code-block:: bash

    beancount-enablebanking --config enablebanking.yaml
    beancount-enablebanking links
    beancount-enablebanking delete-link --session-id <SESSION_ID>

Reference
---------

.. automodule:: beancount_openbanking.cli
   :members:
   :undoc-members:
   :show-inheritance:
