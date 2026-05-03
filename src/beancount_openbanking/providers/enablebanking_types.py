"""Enable Banking API response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def to_camel(snake_str: str) -> str:
    """Convert a snake_case string to camelCase."""
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


class EnableBankingAccountIdentifier(BaseModel):
    """Account identifier (IBAN or other scheme)."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    iban: str | None = None
    other: dict[str, Any] | None = None


class EnableBankingAccountDetail(BaseModel):
    """Account detail as returned by GET /accounts/{id}/details."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

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


class EnableBankingBalanceAmount(BaseModel):
    """Balance amount schema."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    amount: str = "0"
    currency: str = ""


class EnableBankingBalance(BaseModel):
    """Balance schema."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    balance_amount: EnableBankingBalanceAmount = Field(
        default_factory=EnableBankingBalanceAmount
    )
    balance_type: str | None = None
    reference_date: str | None = None


class EnableBankingTransactionAmount(BaseModel):
    """Transaction amount schema."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    amount: str = "0"
    currency: str = ""


class EnableBankingTransaction(BaseModel):
    """Transaction schema."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

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


class EnableBankingAspsp(BaseModel):
    """ASPSP (bank) reference inside a session."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str | None = None
    country: str | None = None


class EnableBankingAccess(BaseModel):
    """Access rights inside a session."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    accounts: list[str] | None = None
    balances: bool | None = None
    transactions: bool | None = None
    valid_until: str | None = None


class EnableBankingSession(BaseModel):
    """Session response schema."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

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
    def from_api_response(cls, data: dict[str, object]) -> "EnableBankingSession":
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
