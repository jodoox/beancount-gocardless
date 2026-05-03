"""Provider implementations and normalized domain models."""

from __future__ import annotations

from .base import (
    Account,
    Balance,
    BookingStatus,
    Provider,
    Transaction,
    TransactionDirection,
)
from .enablebanking import EnableBankingProvider
from .enablebanking_types import EnableBankingAspsp, EnableBankingSession
from .gocardless import GoCardlessProvider
from .gocardless_types import Institution, Requisition
from .utils import BALANCE_TYPE_PRIORITY, coalesce_field, iban_to_currency

__all__ = [
    "Account",
    "Balance",
    "BALANCE_TYPE_PRIORITY",
    "BookingStatus",
    "EnableBankingAspsp",
    "EnableBankingProvider",
    "EnableBankingSession",
    "GoCardlessProvider",
    "Institution",
    "Provider",
    "Requisition",
    "Transaction",
    "TransactionDirection",
    "build_provider",
    "coalesce_field",
    "iban_to_currency",
]


def build_provider(config: object) -> Provider:
    """Instantiate the correct provider for a config object."""

    from ..config import EnableBankingConfig, GoCardlessConfig

    if isinstance(config, GoCardlessConfig):
        return GoCardlessProvider(
            secret_id=config.secret_id,
            secret_key=config.secret_key,
            cache_options=config.cache_options or None,
        )
    if isinstance(config, EnableBankingConfig):
        return EnableBankingProvider(
            application_id=config.application_id,
            private_key_path=config.private_key_path,
            redirect_url=config.redirect_url,
            session_store_path=config.session_store_path,
            cache_options=config.cache_options or None,
        )
    raise TypeError(f"unsupported config type: {type(config)!r}")
