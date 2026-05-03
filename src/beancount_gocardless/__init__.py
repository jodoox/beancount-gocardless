"""Shim for backward compatibility with beancount-gocardless.

This package provides a shim for those who were using the original
beancount-gocardless library before it was refactored to beancount-openbanking
to support multiple bank transaction providers.
"""

from __future__ import annotations

import os
import warnings

if os.getenv("BEANCOUNT_OPENBANKING_SILENCE_RENAME_WARNING") != "1":
    warnings.warn(
        "The package is currently published as 'beancount-gocardless', but a "
        "rename to 'beancount-openbanking' is planned in a future release. "
        "Please update your imports from 'beancount_gocardless' to "
        "'beancount_openbanking' and use the new generic 'BankImporter'. "
        "Set BEANCOUNT_OPENBANKING_SILENCE_RENAME_WARNING=1 to suppress this "
        "warning.",
        DeprecationWarning,
        stacklevel=2,
    )

from beancount_openbanking.providers.gocardless import (
    GoCardlessProvider as GoCardlessClient,
)
from .importer import GoCardlessImporter

# Export models for convenience
from .models import (
    Account,
    Balance,
    BookingStatus,
    Transaction,
    TransactionDirection,
)

__all__ = [
    "GoCardlessImporter",
    "GoCardlessClient",
    "GoCardLessImporter",
    "GoCardLessClient",
    "Account",
    "Balance",
    "BookingStatus",
    "Transaction",
    "TransactionDirection",
]


# Preserve the historic spellings used by the original package.
GoCardLessImporter = GoCardlessImporter
GoCardLessClient = GoCardlessClient
