"""Provider-facing domain models and the Provider protocol."""

from __future__ import annotations

import logging
from datetime import date
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

__all__ = [
    "Account",
    "Balance",
    "BookingStatus",
    "Provider",
    "Transaction",
    "TransactionDirection",
]


class BookingStatus(str, Enum):
    """Normalized booking state for imported transactions."""

    BOOKED = "booked"
    PENDING = "pending"


class TransactionDirection(str, Enum):
    """Normalized transaction direction."""

    CREDIT = "credit"
    DEBIT = "debit"


class Account(BaseModel):
    """Normalized account representation."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str | None = None
    currency: str | None = None
    iban: str | None = None
    provider_data: dict[str, Any] = Field(default_factory=dict)


class Balance(BaseModel):
    """Normalized balance representation."""

    model_config = ConfigDict(extra="allow")

    amount: str
    currency: str
    balance_type: str | None = None
    reference_date: str | None = None
    provider_data: dict[str, Any] = Field(default_factory=dict)


class Transaction(BaseModel):
    """Normalized transaction representation."""

    model_config = ConfigDict(extra="allow")

    transaction_id: str | None = None
    entry_reference: str | None = None
    booking_date: str | None = None
    value_date: str | None = None
    transaction_date: str | None = None
    amount: str
    currency: str
    direction: TransactionDirection | None = None
    booking_status: BookingStatus
    remittance_information: list[str] = Field(default_factory=list)
    creditor_name: str | None = None
    debtor_name: str | None = None
    provider_data: dict[str, Any] = Field(default_factory=dict)


class Provider(Protocol):
    """Protocol implemented by bank data providers."""

    def list_accounts(self) -> list[Account]: ...
    def get_balances(self, account_id: str) -> list[Balance]: ...
    def get_transactions(
        self,
        account_id: str,
        booked_from: date | None = None,
        booked_to: date | None = None,
    ) -> list[Transaction]: ...
