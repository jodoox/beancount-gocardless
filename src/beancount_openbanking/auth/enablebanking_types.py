"""Enable Banking OAuth session model and supporting types.

These types describe the shape of an Enable Banking authorization session
(including the accounts the user granted access to) and live in ``auth/``
because they are owned by the authorization flow, not by the data-fetching
provider.

Provider-specific balance and transaction shapes remain in
``providers/enablebanking_types.py``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def to_camel(snake_str: str) -> str:
    """Convert a snake_case string to camelCase."""
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


class _CamelModel(BaseModel):
    """Base model with camelCase alias generator."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class EnableBankingAccountIdentifier(_CamelModel):
    """Account identifier (IBAN or other scheme)."""

    iban: str | None = None
    other: dict[str, Any] | None = None


class EnableBankingAccountDetail(_CamelModel):
    """Account detail as returned by GET /accounts/{id}/details."""

    uid: str
    name: str | None = None
    currency: str | None = None
    account_id: EnableBankingAccountIdentifier | None = None
    cash_account_type: str | None = None
    product: str | None = None
    usage: str | None = None
    psu_status: str | None = None
    details: str | None = None
    identification_hash: str | None = None
    identification_hashes: list[str] = Field(default_factory=list)


class EnableBankingAspsp(_CamelModel):
    """ASPSP (bank) reference inside a session."""

    name: str | None = None
    country: str | None = None


class EnableBankingAccess(_CamelModel):
    """Access rights inside a session."""

    accounts: list[str] | None = None
    balances: bool | None = None
    transactions: bool | None = None
    valid_until: str | None = None


class EnableBankingSession(_CamelModel):
    """Session response schema."""

    session_id: str | None = None
    accounts: list[str] = Field(default_factory=list)
    accounts_data: list[EnableBankingAccountDetail] = Field(default_factory=list)
    aspsp: EnableBankingAspsp | None = None
    psu_type: str | None = None
    access: EnableBankingAccess | None = None
    status: str | None = None
    psu_id_hash: str | None = None
    created: str | None = None
    authorized: str | None = None
    closed: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "EnableBankingSession":
        """Build from raw API dict, handling both new and legacy formats."""
        raw_accounts = data.get("accounts", [])
        accounts_data: list[EnableBankingAccountDetail] = []

        # New format: accounts is list of UUID strings, details in accounts_data
        if raw_accounts and isinstance(raw_accounts[0], str):
            accounts = raw_accounts
            for item in data.get("accounts_data", []):
                if isinstance(item, dict):
                    accounts_data.append(
                        EnableBankingAccountDetail.model_validate(item)
                    )
        else:
            # Legacy format: accounts is list of dicts
            accounts = []
            for item in raw_accounts:
                if isinstance(item, dict):
                    accounts.append(item.get("uid", ""))
                    accounts_data.append(
                        EnableBankingAccountDetail.model_validate(item)
                    )

        aspsp_raw = data.get("aspsp")
        access_raw = data.get("access")

        return cls(
            session_id=data.get("session_id"),
            accounts=accounts,
            accounts_data=accounts_data,
            aspsp=EnableBankingAspsp.model_validate(aspsp_raw) if aspsp_raw else None,
            psu_type=data.get("psu_type"),
            access=EnableBankingAccess.model_validate(access_raw)
            if access_raw
            else None,
            status=data.get("status"),
            psu_id_hash=data.get("psu_id_hash"),
            created=data.get("created"),
            authorized=data.get("authorized"),
            closed=data.get("closed"),
        )


__all__ = [
    "EnableBankingAccess",
    "EnableBankingAccountDetail",
    "EnableBankingAccountIdentifier",
    "EnableBankingAspsp",
    "EnableBankingSession",
]
