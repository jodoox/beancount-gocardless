"""Minimal GoCardless API response models used by the package."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Institution(BaseModel):
    """GoCardless institution metadata."""

    id: str
    name: str
    bic: str | None = None
    transaction_total_days: str
    countries: list[str]
    logo: str | None = None
    supported_features: list[str] | None = None
    supported_payments: dict[str, Any] | None = None


class Requisition(BaseModel):
    """GoCardless requisition."""

    id: str
    created: str
    redirect: str
    status: str
    institution_id: str
    reference: str
    accounts: list[str] = Field(default_factory=list)
    link: str | None = None
    agreement: str | None = None
    user_language: str | None = None
    account_selection: bool | None = None
    redirect_immediate: bool | None = None
