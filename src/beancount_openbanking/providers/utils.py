"""Shared helpers for provider implementations."""

from __future__ import annotations

from .base import TransactionDirection


def normalize_transaction_direction(
    value: str | None,
) -> TransactionDirection | None:
    """Normalize provider-specific direction codes."""

    if value is None:
        return None

    normalized = value.upper()
    if normalized in {"CRDT", "CREDIT"}:
        return TransactionDirection.CREDIT
    if normalized in {"DBIT", "DEBIT"}:
        return TransactionDirection.DEBIT
    return None
