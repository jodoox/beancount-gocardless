Compatibility
=============

Naming
------

The project keeps ``beancount-gocardless`` as the public distribution name for
now.

Current naming:

* PyPI distribution: ``beancount-gocardless``
* Python package: ``beancount_openbanking``
* Primary multi-provider CLI: ``beancount-openbanking``
* Dedicated GoCardless helper CLI: ``beancount-gocardless``
* Dedicated Enable Banking helper CLI: ``beancount-enablebanking``

This is intentional for the current release line so the package name stays
stable while the broader provider architecture continues to mature.

The legacy ``beancount_gocardless`` shim remains available for import
compatibility, including its historic class aliases.
