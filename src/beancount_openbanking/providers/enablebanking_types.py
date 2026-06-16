"""Enable Banking API response models for account data.

Session and account-detail shapes live in
``auth/enablebanking_types.py`` because they are owned by the
authorization flow. This module keeps the balance and transaction shapes
that ``EnableBankingProvider`` consumes when fetching account data.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..auth.enablebanking_types import to_camel


class _CamelModel(BaseModel):
    """Base model with camelCase alias generator."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class EnableBankingBalanceAmount(_CamelModel):
    """Balance amount schema."""

    amount: str = "0"
    currency: str = ""


class EnableBankingBalance(_CamelModel):
    """Balance schema."""

    balance_amount: EnableBankingBalanceAmount = Field(
        default_factory=EnableBankingBalanceAmount
    )
    balance_type: str | None = None
    reference_date: str | None = None


class EnableBankingTransactionAmount(_CamelModel):
    """Transaction amount schema."""

    amount: str = "0"
    currency: str = ""


class EnableBankingTransaction(_CamelModel):
    """Transaction schema."""

    transaction_id: str | None = None
    entry_reference: str | None = None
    booking_date: str | None = None
    value_date: str | None = None
    transaction_date: str | None = None
    transaction_amount: EnableBankingTransactionAmount = Field(
        default_factory=EnableBankingTransactionAmount
    )
    credit_debit_indicator: str | None = None
    remittance_information: list[str] = Field(default_factory=list)
    remittance_information_unstructured: str | None = None
    remittance_information_unstructured_array: list[str] = Field(default_factory=list)
    creditor_name: str | None = None
    debtor_name: str | None = None
    status: str | None = None


__all__ = [
    "EnableBankingBalance",
    "EnableBankingBalanceAmount",
    "EnableBankingTransaction",
    "EnableBankingTransactionAmount",
]
