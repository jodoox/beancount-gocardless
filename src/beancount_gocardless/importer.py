"""Deprecated: use beancount_openbanking.importer instead.

This module provides a GoCardlessImporter class for backward compatibility.
"""

from __future__ import annotations

import logging
from pathlib import Path
from beancount_openbanking.importer import BankImporter, MetadataRefComparator
from beancount_openbanking.config import ImportConfig, load_config

logger = logging.getLogger(__name__)


class GoCardlessImporter(BankImporter):
    """Backward compatible GoCardless importer."""

    def __init__(self, config_filepath: str = "gocardless.yaml") -> None:
        super().__init__(config_filepath=config_filepath)

    def load_config(self, filepath: str) -> ImportConfig:
        self.config = load_config(filepath, default_provider="gocardless")
        return self.config

    DEFAULT_METADATA_FIELDS = {
        "nordref": "transaction_id",
        "creditorName": "creditor_name",
        "debtorName": "debtor_name",
        "bookingDate": "booking_date",
    }
    cmp = MetadataRefComparator(["nordref"])

    def identify(self, filepath: str) -> bool:
        """Identify if the file is a GoCardless config file.

        Backward compatibility: also matches if the filename is gocardless.yaml.
        """
        path = Path(filepath).expanduser().resolve()
        if path.name in ("gocardless.yaml", "gocardless.yml"):
            return True
        return super().identify(filepath)

    def get_narration(self, transaction) -> str:
        """Override to clean narration strings."""
        logger.info(transaction)
        narration = super().get_narration(transaction)
        if narration:
            return " ".join(narration.replace("\\", " ").split())
        return ""

    def get_transaction_status(self, transaction) -> str:
        return self.get_transaction_flag(transaction)


GoCardLessImporter = GoCardlessImporter

__all__ = ["GoCardlessImporter", "GoCardLessImporter"]
