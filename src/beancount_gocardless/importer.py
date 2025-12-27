import logging
from datetime import date, timedelta
from os import path
from typing import Dict, List, Optional, Any, Tuple
import beangulp
import yaml
from beancount.core import amount, data, flags
from beancount.core.number import D

from .client import GoCardlessClient
from .models import BankTransaction, GoCardlessConfig

logger = logging.getLogger(__name__)


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
    An importer for GoCardless API with improved structure and extensibility.

    Attributes:
        config (Optional[GoCardlessConfig]): Configuration loaded from the YAML file.
        _client (Optional[GoCardlessClient]): Instance of the GoCardless API client.
    """

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
        self, transaction: BankTransaction, custom_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extracts metadata from a transaction and returns it as a dictionary.

        This method can be overridden in subclasses to customize metadata extraction.

        Args:
            transaction (BankTransaction): The transaction data from the API.
            custom_metadata (Dict[str, Any]): Custom metadata from the config file.

        Returns:
            Dict[str, Any]: A dictionary of metadata key-value pairs.
        """
        metakv: Dict[str, Any] = {}

        # Transaction ID
        if transaction.transaction_id:
            metakv["nordref"] = transaction.transaction_id

        # Names
        if transaction.creditor_name:
            metakv["creditorName"] = transaction.creditor_name
        if transaction.debtor_name:
            metakv["debtorName"] = transaction.debtor_name

        # Currency exchange
        if (
            transaction.currency_exchange
            and transaction.currency_exchange[0].instructed_amount
        ):
            instructedAmount = transaction.currency_exchange[0].instructed_amount
            metakv["original"] = (
                f"{instructedAmount.currency} {instructedAmount.amount}"
            )

        if transaction.booking_date:
            metakv["bookingDate"] = transaction.booking_date

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
    ) -> Optional[data.Transaction]:
        """
        Creates a Beancount transaction entry from a GoCardless transaction.

        This method can be overridden in subclasses to customize entry creation.

        Args:
            transaction (Dict[str, Any]): The transaction data from the API.
            status (str): The transaction status ('booked' or 'pending').
            asset_account (str): The Beancount asset account.
            custom_metadata (Dict[str, Any]): Custom metadata from config

        Returns:
            Optional[data.Transaction]: The created Beancount transaction entry, or None if date is invalid.
        """
        logger.debug(
            "Creating entry for transaction %s (%s)", transaction.transaction_id, status
        )
        metakv = self.add_metadata(transaction, custom_metadata)
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
                    transaction, status, asset_account, custom_metadata
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
            expected_balance = None
            other_balances = []
            for bal in balances.balances:
                if bal.balance_type == "expected":
                    expected_balance = bal
                else:
                    other_balances.append(bal)

            if expected_balance:
                balance_amount = amount.Amount(
                    D(str(expected_balance.balance_amount.amount)),
                    expected_balance.balance_amount.currency,
                )
                balance_meta = {}
                balance_amounts = [
                    D(str(b.balance_amount.amount)) for b in balances.balances
                ]
                if len(set(balance_amounts)) > 1:
                    detail_parts = [
                        f"{b.balance_type}: {b.balance_amount.amount} {b.balance_amount.currency}"
                        for b in balances.balances
                    ]
                    detail = " / ".join(detail_parts)
                    balance_meta["detail"] = detail
                # Include custom metadata from config for consistency with transactions
                balance_meta.update(custom_metadata)
                meta = data.new_metadata("", 0, balance_meta)
                balance_entry = data.Balance(
                    meta=meta,
                    date=date.today() + timedelta(days=1),
                    account=asset_account,
                    amount=balance_amount,
                    tolerance=None,
                    diff_amount=None,
                )
                entries.append(balance_entry)
                logger.debug(
                    "Added balance assertion for account %s using expected balance: %s %s",
                    account_id,
                    balance_amount,
                    date.today() + timedelta(days=1),
                )

                # Log other balances if they differ from expected
                expected_amount = D(str(expected_balance.balance_amount.amount))
                for bal in other_balances:
                    other_amount = D(str(bal.balance_amount.amount))
                    if other_amount != expected_amount:
                        logger.info(
                            "Account %s has different balance for type %s: %s %s vs expected %s",
                            account_id,
                            bal.balance_type,
                            other_amount,
                            bal.balance_amount.currency,
                            expected_amount,
                        )

        logger.info(
            "Processed %d total transactions across %d accounts, created %d entries",
            total_transactions,
            len(accounts),
            len(entries),
        )
        return entries

    cmp = ReferenceDuplicatesComparator(["nordref"])
