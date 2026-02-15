import logging
from datetime import date, timedelta
from os import path
from typing import Any, Dict, List, Optional, Tuple

import beangulp
import yaml
from beancount.core import amount, data, flags
from beancount.core.number import D

from .client import GoCardlessClient
from .models import AccountConfig, BankTransaction, GoCardlessConfig

logger = logging.getLogger(__name__)


class ReferenceDuplicatesComparator:
    """Compare two Beancount transactions for duplicate detection.

    Two entries are considered duplicates if they share at least one common
    value among the specified metadata reference keys.

    Args:
        refs: Metadata keys to compare (default: ``["ref"]``).
    """

    def __init__(self, refs: List[str] = ["ref"]) -> None:
        self.refs = refs

    def __call__(self, entry1: data.Transaction, entry2: data.Transaction) -> bool:
        """Return ``True`` if the two entries share any reference value."""
        entry1_refs = set()
        entry2_refs = set()
        for ref in self.refs:
            if ref in entry1.meta:
                entry1_refs.add(entry1.meta[ref])
            if ref in entry2.meta:
                entry2_refs.add(entry2.meta[ref])

        return bool(entry1_refs & entry2_refs)


class GoCardlessImporter(beangulp.Importer):
    """GoCardless API importer for Beancount.

    Fetches transactions from the GoCardless Bank Account Data API and
    converts them into Beancount directives.

    Attributes:
        config: Configuration loaded from YAML.
        _client: GoCardless API client instance.
    """

    NARRATION_SEPARATOR: str = " "

    DEFAULT_METADATA_FIELDS: Dict[str, str] = {
        "nordref": "transactionId",
        "creditorName": "creditorName",
        "debtorName": "debtorName",
        "bookingDate": "bookingDate",
    }

    def __init__(self) -> None:
        """Initialize the GoCardlessImporter."""
        logger.debug("Initializing GoCardlessImporter")
        self.config: Optional[GoCardlessConfig] = None
        self._client: Optional[GoCardlessClient] = None

    @property
    def client(self) -> GoCardlessClient:
        """Lazily initialize and return the GoCardless API client.

        Returns:
            The initialized GoCardless API client.

        Raises:
            ValueError: If config is not loaded.
        """
        if not self._client:
            if not self.config:
                raise ValueError("Config not loaded. Call load_config() first.")
            self._client = GoCardlessClient(
                self.config.secret_id,
                self.config.secret_key,
                cache_options=self.config.cache_options or None,
            )

        return self._client

    def identify(self, filepath: str) -> bool:
        """Identify if the given file is a GoCardless configuration file.

        Args:
            filepath: The path to the file.

        Returns:
            True if the file is a GoCardless configuration file.
        """
        result = path.basename(filepath).endswith("gocardless.yaml")
        logger.debug("Identifying file %s: %s", filepath, result)
        return result

    def account(self, filepath: str) -> str:
        """Return an empty string as account (derived from config instead).

        Args:
            filepath: The path to the file (unused).

        Returns:
            An empty string.
        """
        logger.debug("Returning account for %s: ''", filepath)
        return ""  # We get the account from the config file

    def load_config(self, filepath: str) -> Optional[GoCardlessConfig]:
        """Load configuration from the specified YAML file.

        Args:
            filepath: The path to the YAML configuration file.

        Returns:
            The loaded configuration. Also sets ``self.config``.
        """
        logger.debug("Loading config from %s", filepath)
        with open(filepath, "r") as f:
            raw_config = f.read()
            expanded_config = path.expandvars(raw_config)
            self.config = GoCardlessConfig(**yaml.safe_load(expanded_config))

        return self.config

    def get_all_transactions(
        self, transactions_dict: Dict[str, List[BankTransaction]], types: List[str]
    ) -> List[Tuple[BankTransaction, str]]:
        """Combine transactions of specified types and sort them by date.

        Args:
            transactions_dict: Transactions grouped by type.
            types: Types to include.

        Returns:
            Sorted list of (transaction, type) tuples.
        """
        all_transactions = []
        for tx_type in types:
            if tx_type in transactions_dict:
                all_transactions.extend(
                    [(tx, tx_type) for tx in transactions_dict[tx_type]]
                )
        return sorted(
            all_transactions,
            key=lambda x: x[0].value_date or x[0].booking_date or "",
        )

    def add_metadata(
        self,
        transaction: BankTransaction,
        custom_metadata: Dict[str, Any],
        account_config: Optional[AccountConfig] = None,
    ) -> Dict[str, Any]:
        """Build the metadata dict for a Beancount transaction entry.

        Merges default metadata fields, per-account custom fields from
        ``account_config``, and any ``custom_metadata`` from the YAML config.
        Fields listed in ``account_config.exclude_default_metadata`` are removed.

        This method can be overridden in subclasses to add extra metadata.

        Args:
            transaction: The source GoCardless transaction.
            custom_metadata: Static metadata dict from the account YAML config.
            account_config: Account-level configuration controlling field inclusion.

        Returns:
            A dict of metadata key-value pairs to attach to the Beancount entry.
        """
        metakv: Dict[str, Any] = {}

        exclude_fields: List[str] = []
        custom_fields: Dict[str, str] = {}

        if account_config is not None:
            exclude_fields = account_config.exclude_default_metadata or []
            custom_fields = account_config.metadata_fields or {}

        # Start with defaults, merge with custom fields
        fields = dict(self.DEFAULT_METADATA_FIELDS)
        fields.update(custom_fields)

        # Remove excluded fields
        for key in exclude_fields:
            fields.pop(key, None)

        for out_key, gcl_path in fields.items():
            if gcl_path is None:
                continue
            val = self._get_gcl_path(transaction, gcl_path)
            if val is None:
                continue

            if (
                out_key == "original"
                and hasattr(val, "currency")
                and hasattr(val, "amount")
            ):
                metakv[out_key] = f"{val.currency} {val.amount}"
            else:
                metakv[out_key] = val

        metakv.update(custom_metadata)
        return metakv

    def get_narration(self, transaction: BankTransaction) -> str:
        """Extract the narration from a transaction.

        This method can be overridden in subclasses to customize narration extraction.

        Args:
            transaction: The transaction data from the API.

        Returns:
            The extracted narration.
        """
        parts = []

        if transaction.remittance_information_unstructured:
            parts.append(transaction.remittance_information_unstructured)

        if transaction.remittance_information_unstructured_array:
            parts.append(
                " ".join(transaction.remittance_information_unstructured_array)
            )

        narration = self.NARRATION_SEPARATOR.join(parts)

        return narration

    def get_payee(self, transaction: BankTransaction) -> str:
        """Extract the payee from a transaction.

        Override in subclasses to customize payee extraction. The default
        implementation returns an empty string.

        Args:
            transaction: The transaction data from the API.

        Returns:
            The extracted payee string (empty by default).
        """
        return ""

    def get_transaction_date(self, transaction: BankTransaction) -> Optional[date]:
        """Extract the transaction date. Prefers value_date, falls back to booking_date.

        This method can be overridden in subclasses to customize date extraction.

        Args:
            transaction: The transaction data from the API.

        Returns:
            The extracted transaction date, or None if no date is found.
        """
        date_str = transaction.value_date or transaction.booking_date
        return date.fromisoformat(date_str) if date_str else None

    def get_transaction_status(
        self,
        transaction: BankTransaction,
        status: str,
        metakv: Dict[str, Any],
        tx_amount: amount.Amount,
        asset_account: str,
    ) -> str:
        """Determine the Beancount flag for a transaction.

        Override in subclasses to customize flag assignment. The default returns
        ``FLAG_OKAY`` for booked transactions and ``FLAG_WARNING`` for pending.

        Args:
            transaction: The transaction data from the API.
            status: Transaction status (``"booked"`` or ``"pending"``).
            metakv: Transaction metadata dict.
            tx_amount: Transaction amount.
            asset_account: The Beancount asset account string.

        Returns:
            A Beancount flag character.
        """
        return flags.FLAG_OKAY if status == "booked" else flags.FLAG_WARNING

    def create_transaction_entry(
        self,
        transaction: BankTransaction,
        status: str,
        asset_account: str,
        custom_metadata: Dict[str, Any],
        account_config: Optional[AccountConfig] = None,
    ) -> Optional[data.Transaction]:
        """Create a Beancount transaction entry from a GoCardless transaction.

        Override in subclasses for full control over entry creation.

        Args:
            transaction: The GoCardless transaction data.
            status: Transaction status (``"booked"`` or ``"pending"``).
            asset_account: The Beancount asset account string.
            custom_metadata: Static metadata dict from the account YAML config.
            account_config: Account-level configuration for metadata options.

        Returns:
            A Beancount ``Transaction`` directive, or ``None`` if the transaction
            has no valid date or amount.
        """
        logger.debug(
            "Creating entry for transaction %s (%s)", transaction.transaction_id, status
        )
        metakv = self.add_metadata(transaction, custom_metadata, account_config)
        meta = data.new_metadata("", 0, metakv)

        trx_date = self.get_transaction_date(transaction)
        if trx_date is None:
            logger.debug(
                "Skipping transaction %s with invalid date", transaction.transaction_id
            )
            return None

        narration = self.get_narration(transaction)
        payee = self.get_payee(transaction)

        # Get transaction amount
        if transaction.transaction_amount is None:
            logger.debug(
                "Skipping transaction %s with no amount", transaction.transaction_id
            )
            return None
        currency = transaction.transaction_amount.currency or (
            self.config.currency if self.config else "EUR"
        )
        tx_amount = amount.Amount(
            D(str(transaction.transaction_amount.amount)),
            currency,
        )

        flag = self.get_transaction_status(
            transaction, status, metakv, tx_amount, asset_account
        )

        return data.Transaction(
            meta,
            trx_date,
            flag,
            payee,
            narration,
            data.EMPTY_SET,
            data.EMPTY_SET,
            [
                data.Posting(
                    asset_account,
                    tx_amount,
                    None,
                    None,
                    None,
                    None,
                ),
            ],
        )

    def extract(
        self, filepath: str, existing_entries: data.Entries = None
    ) -> data.Entries:
        """Extract Beancount entries from GoCardless transactions.

        Duplicate detection is handled by the beangulp base class using
        :attr:`cmp`.

        Args:
            filepath: The path to the YAML configuration file.
            existing_entries: Previously extracted entries (used by the base class).

        Returns:
            A list of Beancount transaction entries.
        """
        logger.info("Starting extraction from %s", filepath)
        self.load_config(filepath)

        if not self.config:
            raise ValueError("No config loaded from YAML file")

        entries: data.Entries = []
        accounts = self.config.accounts
        total_transactions = 0
        logger.info("Processing %d accounts", len(accounts))
        for account in accounts:
            account_id = account.id
            asset_account = account.asset_account
            custom_metadata = account.metadata

            logger.debug("Fetching transactions for account %s", account_id)
            account_transactions = self.client.get_account_transactions(account_id)
            transactions_dict = account_transactions.transactions
            all_transactions = self.get_all_transactions(
                transactions_dict, account.transaction_types
            )
            booked_count = len(transactions_dict.get("booked", []))
            pending_count = len(transactions_dict.get("pending", []))
            logger.debug(
                "Fetched %d booked and %d pending transactions for account %s",
                booked_count,
                pending_count,
                account_id,
            )
            total_transactions += sum(
                len(transactions_dict.get(t, [])) for t in account.transaction_types
            )

            skipped = 0
            for transaction, status in all_transactions:
                entry = self.create_transaction_entry(
                    transaction, status, asset_account, custom_metadata, account
                )
                if entry is not None:
                    entries.append(entry)
                else:
                    skipped += 1
            if skipped > 0:
                logger.warning(
                    "Skipped %d invalid transactions for account %s",
                    skipped,
                    account_id,
                )

            # Add balance assertion at the end of the account's transactions
            balances = self.client.get_account_balances(account_id)
            logger.debug(
                "Available balances for account %s: %s",
                account_id,
                [
                    (b.balance_type, b.balance_amount.amount, b.balance_amount.currency)
                    for b in balances.balances
                ],
            )

            # Prioritized balance selection
            priority = {
                "expected": 0,
                "closingBooked": 1,
                "interimBooked": 2,
                "interimAvailable": 3,
                "openingBooked": 4,
            }
            if account.preferred_balance_type:
                priority[account.preferred_balance_type] = -1

            # Sort balances based on priority, with unknown types at the end
            sorted_balances = sorted(
                balances.balances, key=lambda b: priority.get(b.balance_type, 99)
            )

            if sorted_balances:
                selected_balance = sorted_balances[0]
                balance_amount = amount.Amount(
                    D(str(selected_balance.balance_amount.amount)),
                    selected_balance.balance_amount.currency,
                )

                # Determine balance date
                if selected_balance.reference_date:
                    try:
                        balance_date = date.fromisoformat(
                            selected_balance.reference_date
                        ) + timedelta(days=1)
                    except ValueError:
                        balance_date = date.today() + timedelta(days=1)
                else:
                    balance_date = date.today() + timedelta(days=1)

                balance_meta = {}

                # Collect all distinct balance values for metadata
                distinct_details = []
                seen_values = set()
                for b in sorted_balances:
                    val_str = f"{b.balance_amount.amount} {b.balance_amount.currency}"
                    if val_str not in seen_values:
                        distinct_details.append(f"{b.balance_type}: {val_str}")
                        seen_values.add(val_str)

                balance_meta["detail"] = " / ".join(distinct_details)

                # Include custom metadata from config for consistency with transactions
                balance_meta.update(custom_metadata)
                meta = data.new_metadata("", 0, balance_meta)

                balance_entry = data.Balance(
                    meta=meta,
                    date=balance_date,
                    account=asset_account,
                    amount=balance_amount,
                    tolerance=None,
                    diff_amount=None,
                )
                entries.append(balance_entry)
                logger.debug(
                    "Added balance assertion for account %s using %s balance: %s %s",
                    account_id,
                    selected_balance.balance_type,
                    balance_amount,
                    balance_date,
                )

        logger.info(
            "Processed %d total transactions across %d accounts, created %d entries",
            total_transactions,
            len(accounts),
            len(entries),
        )
        return entries

    def _get_gcl_path(self, root: Any, dotted: str) -> Any:
        """Resolve a dotted path against a nested object/dict structure.

        Supports traversal of Pydantic models (by field name or alias),
        plain dicts, and lists (by numeric index).

        Args:
            root: The root object to traverse.
            dotted: A dot-separated path string (e.g. ``"creditorAccount.iban"``).

        Returns:
            The resolved value, or ``None`` if any segment cannot be resolved
            or the final value is a dict/list.
        """
        cur: Any = root
        for seg in dotted.split("."):
            if cur is None:
                return None

            if isinstance(cur, list):
                if not seg.isdigit():
                    return None
                idx = int(seg)
                if idx >= len(cur):
                    return None
                cur = cur[idx]
                continue

            if isinstance(cur, dict):
                cur = cur.get(seg)
                continue

            if hasattr(cur, seg):
                cur = getattr(cur, seg)
                continue

            if hasattr(type(cur), "model_fields"):
                model_fields = type(cur).model_fields
                name = next(
                    (n for n, f in model_fields.items() if f.alias == seg), None
                )
                if name and hasattr(cur, name):
                    cur = getattr(cur, name)
                    continue

            return None

        if isinstance(cur, (dict, list)):
            return None
        return cur

    cmp = ReferenceDuplicatesComparator(["nordref"])
