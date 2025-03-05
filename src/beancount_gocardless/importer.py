from datetime import date
from os import path
import beangulp
import yaml
from beancount.core import amount, data, flags
from beancount.core.number import D
from .client import NordigenClient


class NordigenImporter(beangulp.Importer):
    """
    An importer for Nordigen API with improved structure and extensibility.

    Attributes:
        config (dict): Configuration loaded from the YAML file.
        _client (NordigenClient): Instance of the Nordigen API client.

    """

    def __init__(self):
        """Initialize the NordigenImporter."""
        self.config = None
        self._client = None

    @property
    def client(self):
        """
        Lazily initializes and returns the Nordigen API client.

        Returns:
            NordigenClient: The initialized Nordigen API client.
        """
        if not self._client:
            self._client = NordigenClient(
                self.config["secret_id"],
                self.config["secret_key"],
                cache_options=self.config.get('cache_options', None),
            )

        return self._client

    def identify(self, filepath: str) -> bool:
        """
        Identifies if the given file is a Nordigen configuration file.

        Args:
            filepath (str): The path to the file.

        Returns:
            bool: True if the file is a Nordigen configuration file, False otherwise.
        """
        return path.basename(filepath).endswith("nordigen.yaml")

    def account(self, filepath: str) -> str:
        """
        Returns an empty string as account (not directly used in this importer).

        Args:
            filepath (str): The path to the file.  Not used in this implementation.

        Returns:
            str: An empty string.
        """
        return ""  # We get the account from the config file

    def load_config(self, filepath: str):
        """
        Loads configuration from the specified YAML file.

        Args:
            filepath (str): The path to the YAML configuration file.

        Returns:
            dict: The loaded configuration dictionary.  Also sets the `self.config` attribute.
        """
        with open(filepath, "r") as f:
            raw_config = f.read()
            expanded_config = path.expandvars(
                raw_config
            )  # Handle environment variables
            self.config = yaml.safe_load(expanded_config)

        return self.config

    def get_transactions_data(self, account_id):
        """
        Retrieves transaction data for a given account ID from the Nordigen API.

        Args:
            account_id (str): The Nordigen account ID.

        Returns:
            dict: The transaction data returned by the API.
        """
        transactions_data = self.client.get_transactions(account_id)

        return transactions_data

    def get_all_transactions(self, transactions_data):
        """
        Combines booked and pending transactions and sorts them by date.

        Args:
            transactions_data (dict): The transaction data from the API,
                containing 'booked' and 'pending' lists.

        Returns:
            list: A sorted list of tuples, where each tuple contains
                a transaction dictionary and its status ('booked' or 'pending').
        """
        all_transactions = [
            (tx, "booked") for tx in transactions_data.get("booked", [])
        ] + [(tx, "pending") for tx in transactions_data.get("pending", [])]
        return sorted(
            all_transactions,
            key=lambda x: x[0].get("valueDate") or x[0].get("bookingDate"),
        )

    def add_metadata(self, transaction, filing_account: str):
        """
        Extracts metadata from a transaction and returns it as a dictionary.

        This method can be overridden in subclasses to customize metadata extraction.

        Args:
            transaction (dict): The transaction data from the API.
            filing_account (str):  The optional filing account from the configuration.

        Returns:
            dict: A dictionary of metadata key-value pairs.
        """
        metakv = {}

        # Transaction ID
        if "transactionId" in transaction:
            metakv["nordref"] = transaction["transactionId"]

        # Names
        if "creditorName" in transaction:
            metakv["creditorName"] = transaction["creditorName"]
        if "debtorName" in transaction:
            metakv["debtorName"] = transaction["debtorName"]

        # Currency exchange
        if "currencyExchange" in transaction:
            instructedAmount = transaction["currencyExchange"]["instructedAmount"]
            metakv["original"] = (
                f"{instructedAmount['currency']} {instructedAmount['amount']}"
            )

        if transaction.get("bookingDate"):
            metakv["bookingDate"] = transaction["bookingDate"]

        if filing_account:
            metakv["filing_account"] = filing_account

        return metakv

    def get_narration(self, transaction):
        """
        Extracts the narration from a transaction.

        This method can be overridden in subclasses to customize narration extraction.

        Args:
            transaction (dict): The transaction data from the API.

        Returns:
            str: The extracted narration.
        """
        narration = ""

        if "remittanceInformationUnstructured" in transaction:
            narration += transaction["remittanceInformationUnstructured"]

        if "remittanceInformationUnstructuredArray" in transaction:
            narration += " ".join(transaction["remittanceInformationUnstructuredArray"])

        return narration

    def get_payee(self, transaction):
        """
        Extracts the payee from a transaction.

        This method can be overridden in subclasses to customize payee extraction.  The default
        implementation returns an empty string.

        Args:
            transaction (dict):  The transaction data from the API.

        Returns:
            str: The extracted payee (or an empty string by default).

        """
        return ""

    def get_transaction_date(self, transaction):
        """
        Extracts the transaction date from a transaction.  Prefers 'valueDate',
        falls back to 'bookingDate'.

        This method can be overridden in subclasses to customize date extraction.

        Args:
            transaction (dict): The transaction data from the API.

        Returns:
            date: The extracted transaction date, or None if no date is found.
        """
        date_str = transaction.get("valueDate") or transaction.get("bookingDate")
        return date.fromisoformat(date_str) if date_str else None

    def get_transaction_status(self, status):
        """
        Determines the Beancount transaction flag based on the transaction status.

        This method can be overridden in subclasses to customize flag assignment. The default
        implementation returns FLAG_OKAY for all transactions.

        Args:
            status (str): The transaction status ('booked' or 'pending').

        Returns:
            str: The Beancount transaction flag.
        """
        # Could be configured to use "!" for pending transactions status == 'pending'
        return flags.FLAG_OKAY

    def create_transaction_entry(
        self, transaction, status, asset_account, filing_account
    ):
        """
        Creates a Beancount transaction entry from a Nordigen transaction.

        This method can be overridden in subclasses to customize entry creation.

        Args:
            transaction (dict): The transaction data from the API.
            status (str): The transaction status ('booked' or 'pending').
            asset_account (str): The Beancount asset account.
            filing_account (str): The optional filing account.

        Returns:
            data.Transaction: The created Beancount transaction entry.
        """
        metakv = self.add_metadata(transaction, filing_account)
        meta = data.new_metadata("", 0, metakv)

        trx_date = self.get_transaction_date(transaction)
        narration = self.get_narration(transaction)
        payee = self.get_payee(transaction)
        flag = self.get_transaction_status(status)

        # Get transaction amount
        tx_amount = amount.Amount(
            D(str(transaction["transactionAmount"]["amount"])),
            transaction["transactionAmount"]["currency"],
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
        Extracts Beancount entries from Nordigen transactions.

        Args:
            filepath (str): The path to the YAML configuration file.
            existing (data.Entries):  Existing Beancount entries (not used in this implementation).

        Returns:
            data.Entries: A list of Beancount transaction entries.
        """
        self.load_config(filepath)

        entries = []
        for account in self.config["accounts"]:
            account_id = account["id"]
            asset_account = account["asset_account"]
            filing_account = account.get("filing_account", None)

            transactions_data = self.get_transactions_data(account_id)
            all_transactions = self.get_all_transactions(transactions_data)

            for transaction, status in all_transactions:
                entry = self.create_transaction_entry(
                    transaction, status, asset_account, filing_account
                )
                entries.append(entry)

        return entries

    def cmp(self, entry1: data.Transaction, entry2: data.Transaction):
        """
        Compares two transactions based on their 'nordref' metadata.

        Used for sorting transactions.  This assumes that 'nordref' is a unique
        identifier for each transaction.

        Args:
           entry1 (data.Transaction): The first transaction.
           entry2 (data.Transaction): The second transaction.

        Returns:
            int: -1 if entry1 < entry2, 0 if entry1 == entry2, 1 if entry1 > entry2.
                 Returns 0 if 'nordref' is not present in both.
        """
        if (
            "nordref" in entry1.meta
            and "nordref" in entry2.meta
            and entry1.meta["nordref"] == entry2.meta["nordref"]
        ):
            return 0  # Consider them equal if nordref matches
        elif (
            "nordref" in entry1.meta
            and "nordref" in entry2.meta
            and entry1.meta["nordref"] < entry2.meta["nordref"]
        ):
            return -1
        elif "nordref" in entry1.meta and "nordref" in entry2.meta:
            return 1
        else:
            return 0
