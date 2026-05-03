"""Shared helpers for provider implementations."""

from __future__ import annotations

from typing import Any

from .base import BookingStatus, TransactionDirection

BALANCE_TYPE_PRIORITY: dict[str, int] = {
    "expected": 0,
    "closingBooked": 1,
    "CLOSING": 1,
    "interimBooked": 2,
    "INTERIM": 2,
    "interimAvailable": 3,
    "openingBooked": 4,
    "OPENING": 4,
}


def coalesce_field(raw: dict[str, Any], *keys: str) -> Any:
    """Return the first non-``None`` value among the given keys."""

    for key in keys:
        value = raw.get(key)
        if value is not None:
            return value
    return None


def normalize_booking_status(
    value: str | None,
    *,
    default: BookingStatus | None = None,
) -> BookingStatus | None:
    """Normalize provider-specific booking status codes."""

    if value is None:
        return default

    normalized = value.upper()
    if normalized in {"BOOK", "BOOKED"}:
        return BookingStatus.BOOKED
    if normalized in {"PDNG", "PENDING"}:
        return BookingStatus.PENDING
    return default


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


IBAN_CURRENCY_MAP: dict[str, str] = {
    "AL": "ALL",
    "AD": "EUR",
    "AT": "EUR",
    "AZ": "AZN",
    "BH": "BHD",
    "BY": "BYN",
    "BE": "EUR",
    "BA": "BAM",
    "BR": "BRL",
    "BG": "BGN",
    "CR": "CRC",
    "HR": "EUR",
    "CY": "EUR",
    "CZ": "CZK",
    "DK": "DKK",
    "DO": "DOP",
    "EG": "EGP",
    "SV": "USD",
    "EE": "EUR",
    "FI": "EUR",
    "FR": "EUR",
    "GE": "GEL",
    "DE": "EUR",
    "GI": "GIP",
    "GR": "EUR",
    "GT": "GTQ",
    "HU": "HUF",
    "IS": "ISK",
    "IE": "EUR",
    "IL": "ILS",
    "IT": "EUR",
    "JO": "JOD",
    "KZ": "KZT",
    "KW": "KWD",
    "LV": "EUR",
    "LB": "LBP",
    "LI": "CHF",
    "LT": "EUR",
    "LU": "EUR",
    "MT": "EUR",
    "MR": "MRU",
    "MU": "MUR",
    "MD": "MDL",
    "MC": "EUR",
    "ME": "EUR",
    "NL": "EUR",
    "MK": "MKD",
    "NO": "NOK",
    "PK": "PKR",
    "PS": "ILS",
    "PL": "PLN",
    "PT": "EUR",
    "RO": "RON",
    "LC": "XCD",
    "SM": "EUR",
    "SA": "SAR",
    "RS": "RSD",
    "SC": "SCR",
    "SK": "EUR",
    "SI": "EUR",
    "ES": "EUR",
    "SE": "SEK",
    "CH": "CHF",
    "TN": "TND",
    "TR": "TRY",
    "UA": "UAH",
    "AE": "AED",
    "GB": "GBP",
    "VA": "EUR",
    "VG": "USD",
    "XK": "EUR",
}


def iban_to_currency(iban: str | None) -> str | None:
    """Infer a currency from the IBAN country prefix."""

    if not iban or len(iban) < 2:
        return None
    return IBAN_CURRENCY_MAP.get(iban[:2].upper())
