"""Open banking importers and provider clients for Beancount."""

from __future__ import annotations

import os
import warnings
from importlib.metadata import PackageNotFoundError, version

from .config import (
    EnableBankingConfig,
    GoCardlessConfig,
    ImportConfig,
    ImportTarget,
    ProviderName,
    load_config,
)
from .importer import BankImporter, MetadataRefComparator
from .providers import (
    Account,
    Balance,
    BookingStatus,
    EnableBankingProvider,
    GoCardlessProvider,
    Institution,
    Provider,
    Requisition,
    Transaction,
    TransactionDirection,
)

__all__ = [
    "Account",
    "Balance",
    "BankImporter",
    "BookingStatus",
    "EnableBankingConfig",
    "EnableBankingProvider",
    "GoCardlessConfig",
    "GoCardlessProvider",
    "ImportConfig",
    "ImportTarget",
    "Institution",
    "MetadataRefComparator",
    "Provider",
    "ProviderName",
    "Requisition",
    "Transaction",
    "TransactionDirection",
    "__version__",
    "load_config",
]


RENAME_WARNING = (
    "The package is currently published as 'beancount-gocardless', but a rename "
    "to 'beancount-openbanking' is planned in a future release. Set "
    "BEANCOUNT_OPENBANKING_SILENCE_RENAME_WARNING=1 to suppress this warning."
)

try:
    __version__ = version("beancount-gocardless")
except PackageNotFoundError:
    __version__ = "0+unknown"


def _warn_about_pending_rename() -> None:
    if os.getenv("BEANCOUNT_OPENBANKING_SILENCE_RENAME_WARNING") == "1":
        return
    warnings.warn(RENAME_WARNING, UserWarning, stacklevel=2)


_warn_about_pending_rename()
