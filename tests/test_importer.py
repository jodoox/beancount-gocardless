"""Tests for importer behavior and Beancount mapping."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, call, patch

from beancount_openbanking.config import ImportTarget
from beancount_openbanking.importer import BankImporter, MetadataRefComparator
from beancount_openbanking.providers import (
    Balance,
    BookingStatus,
    Transaction,
    TransactionDirection,
)


class TestBankImporterMetadata:
    def test_add_metadata_basic(self) -> None:
        importer = BankImporter()
        transaction = Transaction(
            transaction_id="tx-123",
            entry_reference="ref-456",
            booking_date="2024-01-15",
            amount="-50.00",
            currency="EUR",
            booking_status=BookingStatus.BOOKED,
            creditor_name="Test Creditor",
            debtor_name="Test Debtor",
        )

        metadata = importer.add_metadata(transaction, {"custom": "value"})

        assert metadata["ref"] == "tx-123"
        assert metadata["creditorName"] == "Test Creditor"
        assert metadata["debtorName"] == "Test Debtor"
        assert metadata["bookingDate"] == "2024-01-15"
        assert metadata["custom"] == "value"

    def test_add_metadata_with_excludes(self) -> None:
        importer = BankImporter()
        transaction = Transaction(
            transaction_id="tx-123",
            booking_date="2024-01-15",
            amount="-50.00",
            currency="EUR",
            booking_status=BookingStatus.BOOKED,
            creditor_name="Test Creditor",
            debtor_name="Test Debtor",
        )
        account_config = ImportTarget(
            id="test",
            asset_account="Assets:Banks:Test",
            exclude_default_metadata=["bookingDate", "creditorName"],
        )

        metadata = importer.add_metadata(transaction, {}, account_config)

        assert "bookingDate" not in metadata
        assert "creditorName" not in metadata
        assert metadata["debtorName"] == "Test Debtor"

    def test_add_metadata_with_provider_path(self) -> None:
        importer = BankImporter()
        transaction = Transaction(
            transaction_id="tx-123",
            booking_date="2024-01-15",
            amount="-50.00",
            currency="EUR",
            booking_status=BookingStatus.BOOKED,
            provider_data={"merchantCategoryCode": "5411"},
        )
        account_config = ImportTarget(
            id="test",
            asset_account="Assets:Banks:Test",
            metadata_fields={"mcc": "merchantCategoryCode"},
        )

        metadata = importer.add_metadata(transaction, {}, account_config)

        assert metadata["mcc"] == "5411"


class TestBankImporterHelpers:
    def test_resolve_dotted_path(self) -> None:
        importer = BankImporter()
        transaction = Transaction(
            transaction_id="tx-123",
            amount="-50.00",
            currency="EUR",
            booking_status=BookingStatus.BOOKED,
            provider_data={
                "additionalDataStructured": {
                    "cardInstrument": {"cardSchemeName": "VISA"}
                }
            },
        )

        value = importer._resolve_transaction_field(
            transaction, "additionalDataStructured.cardInstrument.cardSchemeName"
        )

        assert value == "VISA"

    def test_get_narration(self) -> None:
        importer = BankImporter()
        transaction = Transaction(
            amount="0",
            currency="EUR",
            booking_status=BookingStatus.BOOKED,
            remittance_information=["Payment", "Invoice 123"],
        )

        assert importer.get_narration(transaction) == "Payment Invoice 123"

    def test_get_payee_uses_direction(self) -> None:
        importer = BankImporter()
        transaction = Transaction(
            amount="-100.00",
            currency="EUR",
            direction=TransactionDirection.DEBIT,
            booking_status=BookingStatus.BOOKED,
            creditor_name="Creditor Corp",
            debtor_name="Debtor Person",
        )

        assert importer.get_payee(transaction) == "Creditor Corp"

    def test_filter_transactions_uses_booking_status(self) -> None:
        importer = BankImporter()
        booked = Transaction(
            amount="10.00",
            currency="EUR",
            booking_date="2024-01-01",
            booking_status=BookingStatus.BOOKED,
        )
        pending = Transaction(
            amount="20.00",
            currency="EUR",
            booking_date="2024-01-02",
            booking_status=BookingStatus.PENDING,
        )

        result = importer.filter_transactions([pending, booked], [BookingStatus.BOOKED])

        assert result == [booked]


class TestMetadataRefComparator:
    def test_duplicate_detection_same_ref(self) -> None:
        comparator = MetadataRefComparator(["ref"])

        from beancount.core import data
        from datetime import date as dt_date

        entry1 = data.Transaction(
            data.new_metadata("", 0, {"ref": "abc123"}),
            dt_date(2024, 1, 1),
            "*",
            "",
            "",
            data.EMPTY_SET,
            data.EMPTY_SET,
            [],
        )
        entry2 = data.Transaction(
            data.new_metadata("", 0, {"ref": "abc123"}),
            dt_date(2024, 1, 1),
            "*",
            "",
            "",
            data.EMPTY_SET,
            data.EMPTY_SET,
            [],
        )

        assert comparator(entry1, entry2) is True


class TestBankImporterCmp:
    def test_cmp_defaults_to_ref(self) -> None:
        importer = BankImporter()
        assert importer.cmp.refs == ["ref"]

    def test_cmp_auto_derives_from_default_metadata_fields(self) -> None:
        class CustomImporter(BankImporter):
            DEFAULT_METADATA_FIELDS = {
                "nordref": "transaction_id",
                "bookingDate": "booking_date",
            }

        importer = CustomImporter()
        assert importer.cmp.refs == ["nordref"]

    def test_explicit_cmp_override_takes_precedence(self) -> None:
        class CustomImporter(BankImporter):
            DEFAULT_METADATA_FIELDS = {"nordref": "transaction_id"}
            cmp = MetadataRefComparator(["foo"])

        importer = CustomImporter()
        assert importer.cmp.refs == ["foo"]

    def test_cmp_falls_back_to_ref_when_no_transaction_id_mapping(self) -> None:
        class CustomImporter(BankImporter):
            DEFAULT_METADATA_FIELDS = {"bookingDate": "booking_date"}

        importer = CustomImporter()
        assert importer.cmp.refs == ["ref"]


class TestBankImporterAccount:
    def test_account_returns_empty_string_when_config_has_no_accounts(self) -> None:
        importer = BankImporter()
        importer.config = MagicMock()
        importer.config.accounts = []
        assert importer.account("any-file.yaml") == ""

    def test_account_returns_first_account_asset_account(self, tmp_path) -> None:
        config_file = tmp_path / "test.yaml"
        config_file.write_text(
            """
provider: gocardless
secret_id: test-id
secret_key: test-key
accounts:
  - id: acc-1
    asset_account: Assets:Banks:First
  - id: acc-2
    asset_account: Assets:Banks:Second
""".strip()
        )

        importer = BankImporter()
        account = importer.account(str(config_file))
        assert account == "Assets:Banks:First"


class TestBankImporterExtract:
    def test_extract_sorts_entries_and_uses_account_days_back(self, tmp_path) -> None:
        config_file = tmp_path / "gocardless.yaml"
        config_file.write_text(
            """
provider: gocardless
secret_id: test-id
secret_key: test-key
accounts:
  - id: acc-2
    asset_account: Assets:Banks:Second
    metadata:
      source: second
    days_back: 10
  - id: acc-1
    asset_account: Assets:Banks:First
    metadata:
      source: first
    days_back: 30
""".strip()
        )

        provider = MagicMock()
        provider.get_transactions.side_effect = lambda account_id, **_: {
            "acc-1": [
                Transaction(
                    transaction_id="tx-1",
                    booking_date="2024-01-15",
                    amount="20.00",
                    currency="EUR",
                    direction=TransactionDirection.CREDIT,
                    booking_status=BookingStatus.BOOKED,
                    debtor_name="Employer",
                    remittance_information=["Salary"],
                )
            ],
            "acc-2": [
                Transaction(
                    transaction_id="tx-2",
                    booking_date="2024-02-02",
                    amount="-10.00",
                    currency="EUR",
                    direction=TransactionDirection.DEBIT,
                    booking_status=BookingStatus.BOOKED,
                    creditor_name="Coffee Shop",
                    remittance_information=["Coffee"],
                )
            ],
        }[account_id]
        provider.get_balances.side_effect = lambda account_id: {
            "acc-1": [
                Balance(
                    amount="200.00",
                    currency="EUR",
                    balance_type="closingBooked",
                    reference_date="2024-01-31",
                )
            ],
            "acc-2": [
                Balance(
                    amount="90.00",
                    currency="EUR",
                    balance_type="closingBooked",
                    reference_date="2024-02-02",
                )
            ],
        }[account_id]

        importer = BankImporter()
        with (
            patch(
                "beancount_openbanking.config.GoCardlessConfig.build_provider",
                return_value=provider,
            ),
            patch.object(importer, "_today", return_value=date(2024, 2, 10)),
        ):
            entries = importer.extract(str(config_file))

        assert [entry.date.isoformat() for entry in entries] == [
            "2024-01-15",
            "2024-02-01",
            "2024-02-02",
            "2024-02-03",
        ]
        assert entries[0].meta["source"] == "first"
        assert entries[2].meta["source"] == "second"
        assert provider.get_transactions.call_args_list == [
            call(
                "acc-2",
                booked_from=date(2024, 1, 31),
                booked_to=date(2024, 2, 10),
            ),
            call(
                "acc-1",
                booked_from=date(2024, 1, 11),
                booked_to=date(2024, 2, 10),
            ),
        ]


class TestTransactionFormatting:
    """Tests for transaction entry formatting (regression tests for blank line bug)."""

    def test_transaction_entry_has_no_blank_line_before_postings(self) -> None:
        """Regression test: formatted transaction should not have blank lines before postings."""
        from beancount.parser import printer
        from beancount_openbanking.providers import BookingStatus

        importer = BankImporter()
        transaction = Transaction(
            transaction_id="23383801094",
            booking_date="2026-02-02",
            amount="22.99",
            currency="EUR",
            booking_status=BookingStatus.BOOKED,
            remittance_information=["Relevé différé Carte 4810********2321"],
        )

        entry = importer.create_transaction_entry(
            transaction=transaction,
            asset_account="Assets:Banque:Bourso:Joint:Checking",
            custom_metadata={},
        )

        formatted = printer.format_entry(entry)

        # Check that metadata line is followed directly by posting line (no blank line)
        assert 'bookingDate: "2026-02-02"\n  Assets:' in formatted, (
            f"Expected metadata followed by posting without blank line. Got:\n{formatted}"
        )

        # Ensure no double newlines before postings
        assert "\n\n  Assets:" not in formatted, (
            f"Found blank line before postings. Got:\n{formatted}"
        )

    def test_transaction_entry_with_two_postings_formatting(self) -> None:
        """Test that transactions with multiple postings are formatted correctly."""
        from beancount.core import data
        from beancount.parser import printer
        from datetime import date as dt_date
        from beancount.core.amount import Amount
        from beancount.core.number import D

        meta = data.new_metadata("", 0, {"ref": "123", "bookingDate": "2026-02-02"})
        entry = data.Transaction(
            meta,
            dt_date(2026, 2, 2),
            "*",
            "Relevé différé Carte 4810********2321",
            "",
            data.EMPTY_SET,
            data.EMPTY_SET,
            [
                data.Posting(
                    "Assets:Banque:Bourso:Joint:Checking",
                    Amount(D("22.99"), "EUR"),
                    None,
                    None,
                    None,
                    None,
                ),
                data.Posting(
                    "Liabilities:Banque:Bourso:Joint:2321",
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            ],
        )

        formatted = printer.format_entry(entry)

        # Verify metadata is followed directly by first posting
        assert 'bookingDate: "2026-02-02"\n  Assets:' in formatted
        # Verify no blank lines within the transaction
        assert "\n\n  " not in formatted
