import logging
from datetime import date, timedelta
from os import path
from typing import Dict, List, Optional, Any, Tuple
import beangulp
import yaml
from beancount.core import amount, data, flags
from beancount.core.number import D

from .client import GoCardlessClient
from .models import BankTransaction, GoCardlessConfig, AccountConfig

logger = logging.getLogger(__name__)


def _flatten_dict(d: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Recursively flatten a nested dict to dotted paths."""
    result: Dict[str, Any] = {}
    for key, value in d.items():
        new_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten_dict(value, new_key))
        else:
            result[new_key] = value
    return result


class ReferenceDuplicatesComparator:
    def __init__(self, refs: List[str] = ["ref"]) -> None:
        self.refs = refs

    def __call__(self, entry1: data.Transaction, entry2: data.Transaction) -> bool:
        entry1Refs = set()
        entry2Refs = set()
        for ref in self.refs:
            if ref in entry1.meta:
                entry1Refs.add(entry1.meta[ref])
            if ref in entry2.meta:
                entry2Refs.add(entry2.meta[ref])

        return bool(entry1Refs & entry2Refs)


class GoCardLessImporter(beangulp.Importer):
    """
    GoCardless API importer for Beancount.

    Attributes:
        config (Optional[GoCardlessConfig]): Configuration loaded from YAML.
        _client (Optional[GoCardlessClient]): GoCardless API client instance.
    """

    DEFAULT_METADATA_FIELDS: Dict[str, str] = {
        "nordref": "transactionId",
        "creditorName": "creditorName",
        "debtorName": "debtorName",
        "bookingDate": "bookingDate",
    }

    def __init__(self) -> None:
        """Initialize the GoCardLessImporter."""
        logger.debug("Initializing GoCardLessImporter")
        self.config: Optional[GoCardlessConfig] = None
        self._client: Optional[GoCardlessClient] = None

    @property
    def client(self) -> GoCardlessClient:
        """
        Lazily initializes and returns the GoCardless API client.

        Returns:
            GoCardlessClient: The initialized GoCardless API client.

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
        """
        Identifies if the given file is a GoCardless configuration file.

        Args:
            filepath (str): The path to the file.

        Returns:
            bool: True if the file is a GoCardless configuration file, False otherwise.
        """
        result = path.basename(filepath).endswith("gocardless.yaml")
        logger.debug("Identifying file %s: %s", filepath, result)
        return result

    def account(self, filepath: str) -> str:
        """
        Returns an empty string as account (not directly used in this importer).

        Args:
            filepath (str): The path to the file. Not used in this implementation.

        Returns:
            str: An empty string.
        """
        logger.debug("Returning account for %s: ''", filepath)
        return ""  # We get the account from the config file

    def load_config(self, filepath: str) -> Optional[GoCardlessConfig]:
        """
        Loads configuration from the specified YAML file.

        Args:
            filepath (str): The path to the YAML configuration file.

        Returns:
            GoCardlessConfig: The loaded configuration. Also sets the `self.config` attribute.
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
        """
        Combines transactions of specified types and sorts them by date.

        Args:
            transactions_dict (Dict[str, List[BankTransaction]]): Transactions by type.
            types (List[str]): Types to include.

        Returns:
            List[Tuple[BankTransaction, str]]: Sorted list of (transaction, type) tuples.
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
        """
        Extracts the narration from a transaction.

        This method can be overridden in subclasses to customize narration extraction.

        Args:
            transaction (BankTransaction): The transaction data from the API.

        Returns:
            str: The extracted narration.
        """
        narration = ""

        if transaction.remittance_information_unstructured:
            narration += transaction.remittance_information_unstructured

        if transaction.remittance_information_unstructured_array:
            narration += " ".join(transaction.remittance_information_unstructured_array)

        return narration

    def get_payee(self, transaction: BankTransaction) -> str:
        """
        Extracts the payee from a transaction.

        This method can be overridden in subclasses to customize payee extraction. The default
        implementation returns an empty string.

        Args:
            transaction (Dict[str, Any]): The transaction data from the API.

        Returns:
            str: The extracted payee (or an empty string by default).
        """
        return ""

    def get_transaction_date(self, transaction: BankTransaction) -> Optional[date]:
        """
        Extracts the transaction date from a transaction. Prefers 'valueDate',
        falls back to 'bookingDate'.

        This method can be overridden in subclasses to customize date extraction.

        Args:
            transaction (BankTransaction): The transaction data from the API.

        Returns:
            Optional[date]: The extracted transaction date, or None if no date is found.
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
        """
        Determines the Beancount transaction flag based on transaction context.

        This method can be overridden in subclasses to customize flag assignment. The default
        implementation returns FLAG_OKAY for booked transactions and FLAG_WARNING for pending.

        Args:
            transaction (Dict[str, Any]): The transaction data from the API.
            status (str): The transaction status ('booked' or 'pending').
            metakv (Dict[str, Any]): Transaction metadata.
            tx_amount (amount.Amount): Transaction amount.
            asset_account (str): The Beancount asset account.

        Returns:
            str: The Beancount transaction flag.
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
        """
        Creates a Beancount transaction entry from a GoCardless transaction.

        This method can be overridden in subclasses to customize entry creation.

        Args:
            transaction (Dict[str, Any]): The transaction data from the API.
            status (str): The transaction status ('booked' or 'pending').
            asset_account (str): The Beancount asset account.
            custom_metadata (Dict[str, Any]): Custom metadata from config
            account_config (Optional[AccountConfig]): Account configuration for metadata options.

        Returns:
            Optional[data.Transaction]: The created Beancount transaction entry, or None if date is invalid.
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
        tx_amount = amount.Amount(
            D(str(transaction.transaction_amount.amount)),
            transaction.transaction_amount.currency,
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

    def extract(self, filepath: str, existing: data.Entries) -> data.Entries:
        """
        Extracts Beancount entries from GoCardless transactions.

        Args:
            filepath (str): The path to the YAML configuration file.
            existing (data.Entries): Existing Beancount entries (not used in this implementation).

        Returns:
            data.Entries: A list of Beancount transaction entries.
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
            PRIORITY = {
                "expected": 0,
                "closingBooked": 1,
                "interimBooked": 2,
                "interimAvailable": 3,
                "openingBooked": 4,
            }
            if account.preferred_balance_type:
                PRIORITY[account.preferred_balance_type] = -1

            # Sort balances based on priority, with unknown types at the end
            sorted_balances = sorted(
                balances.balances, key=lambda b: PRIORITY.get(b.balance_type, 99)
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
