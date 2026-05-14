"""Beancount importer for normalized bank data providers."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
import beangulp
from beancount.core import amount, data, flags
from beancount.core.number import D

from .config import (
    ImportConfig,
    ImportTarget,
    load_config,
)
from .providers import (
    BALANCE_TYPE_PRIORITY,
    Balance,
    BookingStatus,
    Provider,
    Transaction,
    TransactionDirection,
    build_provider,
)

logger = logging.getLogger(__name__)
ZERO = D("0")

__all__ = ["BankImporter"]


class MetadataRefComparator:
    """Compare Beancount transactions by configured metadata references."""

    def __init__(self, refs: list[str] | None = None) -> None:
        self.refs = refs if refs is not None else ["ref"]

    def __call__(self, entry1: data.Transaction, entry2: data.Transaction) -> bool:
        entry1_refs = {entry1.meta[ref] for ref in self.refs if ref in entry1.meta}
        entry2_refs = {entry2.meta[ref] for ref in self.refs if ref in entry2.meta}
        return bool(entry1_refs & entry2_refs)


class BankImporter(beangulp.Importer):
    """Import transactions from a configured provider into Beancount."""

    NARRATION_SEPARATOR = " "
    DEFAULT_METADATA_FIELDS: dict[str, str] = {
        "ref": "transaction_id",
        "creditorName": "creditor_name",
        "debtorName": "debtor_name",
        "bookingDate": "booking_date",
    }

    def __init__(self, config_filepath: str = "openbanking.yml") -> None:
        self.config_filepath = Path(config_filepath).expanduser().resolve()
        self.config: ImportConfig | None = None
        if "cmp" not in self.__class__.__dict__:
            self.cmp = self._build_cmp()

    @property
    def provider(self) -> Provider:
        if self.config is None:
            raise ValueError("Config not loaded. Call load_config() first.")
        return build_provider(self.config)

    def identify(self, filepath: str) -> bool:
        return Path(filepath).expanduser().resolve() == self.config_filepath

    def account(self, filepath: str) -> str:
        if self.config is None:
            self.load_config(filepath)
        if self.config is not None and self.config.accounts:
            return self.config.accounts[0].asset_account
        return ""

    def load_config(self, filepath: str) -> ImportConfig:
        self.config = load_config(filepath)
        return self.config

    def _today(self) -> date:
        return date.today()

    def filter_transactions(
        self,
        transactions: list[Transaction],
        booking_statuses: list[BookingStatus],
    ) -> list[Transaction]:
        allowed_statuses = set(booking_statuses)
        filtered = [tx for tx in transactions if tx.booking_status in allowed_statuses]
        return sorted(filtered, key=lambda tx: tx.value_date or tx.booking_date or "")

    def add_metadata(
        self,
        transaction: Transaction,
        custom_metadata: dict[str, object],
        account_config: ImportTarget | None = None,
    ) -> dict[str, object]:
        metadata: dict[str, object] = {}

        excluded_keys: list[str] = []
        custom_fields: dict[str, str] = {}
        if account_config is not None:
            excluded_keys = account_config.exclude_default_metadata or []
            custom_fields = account_config.metadata_fields or {}

        field_map = dict(self.DEFAULT_METADATA_FIELDS)
        field_map.update(custom_fields)
        for key in excluded_keys:
            field_map.pop(key, None)

        for output_key, field_name in field_map.items():
            value = self._resolve_transaction_field(transaction, field_name)
            if value is not None:
                metadata[output_key] = value

        metadata.update(custom_metadata)
        return metadata

    def _resolve_transaction_field(
        self,
        transaction: Transaction,
        field_name: str,
    ) -> object:
        if "." not in field_name:
            value = getattr(transaction, field_name, None)
            if value is not None:
                return value

        if transaction.provider_data:
            return self._resolve_dotted_path(transaction.provider_data, field_name)
        return None

    def _resolve_dotted_path(self, root: object, dotted_path: str) -> object:
        current = root
        for segment in dotted_path.split("."):
            if current is None:
                return None
            if isinstance(current, list):
                if not segment.isdigit():
                    return None
                index = int(segment)
                if index >= len(current):
                    return None
                current = current[index]
                continue
            if isinstance(current, dict):
                current = current.get(segment)
                continue
            if hasattr(current, segment):
                current = getattr(current, segment)
                continue
            return None

        if isinstance(current, (dict, list)):
            return None
        return current

    def get_narration(self, transaction: Transaction) -> str:
        return self.NARRATION_SEPARATOR.join(
            part for part in transaction.remittance_information if part
        )

    def get_payee(self, transaction: Transaction) -> str:
        if transaction.direction == TransactionDirection.CREDIT:
            return transaction.debtor_name or ""
        if transaction.direction == TransactionDirection.DEBIT:
            return transaction.creditor_name or ""
        if D(str(transaction.amount)) >= ZERO:
            return transaction.debtor_name or transaction.creditor_name or ""
        return transaction.creditor_name or transaction.debtor_name or ""

    def create_transaction_entry(
        self,
        transaction: Transaction,
        asset_account: str,
        custom_metadata: dict[str, object],
        account_config: ImportTarget | None = None,
    ) -> data.Transaction | None:
        transaction_date = transaction.value_date or transaction.booking_date
        if transaction_date is None or transaction.amount is None:
            return None

        entry_date = date.fromisoformat(transaction_date)

        metadata = self.add_metadata(transaction, custom_metadata, account_config)
        config_currency = self.config.currency if self.config is not None else None
        transaction_amount = amount.Amount(
            D(str(transaction.amount)),
            transaction.currency or config_currency or "EUR",
        )
        flag = (
            flags.FLAG_OKAY
            if transaction.booking_status == BookingStatus.BOOKED
            else flags.FLAG_WARNING
        )
        return data.Transaction(
            data.new_metadata("", 0, metadata),
            entry_date,
            flag,
            self.get_payee(transaction),
            self.get_narration(transaction),
            data.EMPTY_SET,
            data.EMPTY_SET,
            [
                data.Posting(
                    asset_account,
                    transaction_amount,
                    None,
                    None,
                    None,
                    None,
                ),
            ],
        )

    def create_balance_entry(
        self,
        asset_account: str,
        balances: list[Balance],
        custom_metadata: dict[str, object],
        preferred_balance_type: str | None = None,
    ) -> data.Balance | None:
        if not balances:
            return None

        priority = dict(BALANCE_TYPE_PRIORITY)
        if preferred_balance_type:
            priority[preferred_balance_type] = -1
        selected_balance = sorted(
            balances,
            key=lambda balance: priority.get(balance.balance_type or "", 99),
        )[0]

        if selected_balance is None:
            return None

        if selected_balance.reference_date:
            try:
                balance_date = date.fromisoformat(
                    selected_balance.reference_date
                ) + timedelta(days=1)
            except ValueError:
                balance_date = self._today() + timedelta(days=1)
        else:
            balance_date = self._today() + timedelta(days=1)

        distinct_details: list[str] = []
        seen_values: set[str] = set()
        for balance in sorted(
            balances,
            key=lambda item: BALANCE_TYPE_PRIORITY.get(item.balance_type or "", 99),
        ):
            value = f"{balance.amount} {balance.currency}"
            if value in seen_values:
                continue
            distinct_details.append(f"{balance.balance_type}: {value}")
            seen_values.add(value)

        metadata = {"detail": " / ".join(distinct_details)}
        metadata.update(custom_metadata)
        return data.Balance(
            meta=data.new_metadata("", 0, metadata),
            date=balance_date,
            account=asset_account,
            amount=amount.Amount(
                D(str(selected_balance.amount)),
                selected_balance.currency,
            ),
            tolerance=None,
            diff_amount=None,
        )

    def _build_cmp(self) -> MetadataRefComparator:
        refs = [
            key
            for key, value in self.DEFAULT_METADATA_FIELDS.items()
            if value == "transaction_id"
        ]
        return MetadataRefComparator(refs if refs else ["ref"])

    def _entry_sort_key(self, entry: data.Directive) -> tuple[date, int, str]:
        secondary = 0 if isinstance(entry, data.Transaction) else 1
        if isinstance(entry, data.Transaction):
            subject = entry.postings[0].account if entry.postings else ""
        else:
            subject = getattr(entry, "account", "")
        return entry.date, secondary, subject

    def extract(
        self,
        filepath: str,
        existing: data.Entries | None = None,
    ) -> data.Entries:
        self.load_config(filepath)
        if self.config is None:
            raise ValueError("No config loaded from YAML file")

        entries: data.Entries = []
        today = self._today()
        provider = self.provider
        for account in self.config.accounts:
            booked_from = today - timedelta(days=account.days_back)
            booked_to = today

            transactions = provider.get_transactions(
                account.id,
                booked_from=booked_from,
                booked_to=booked_to,
            )
            filtered_transactions = self.filter_transactions(
                transactions,
                account.booking_statuses,
            )

            for transaction in filtered_transactions:
                entry = self.create_transaction_entry(
                    transaction,
                    account.asset_account,
                    account.metadata,
                    account,
                )
                if entry is not None:
                    entries.append(entry)

            balance_entry = self.create_balance_entry(
                account.asset_account,
                provider.get_balances(account.id),
                account.metadata,
                account.preferred_balance_type,
            )
            if balance_entry is not None:
                entries.append(balance_entry)
        entries.sort(key=self._entry_sort_key)
        return entries
