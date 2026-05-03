"""Tests for backward compatibility shim in beancount_gocardless."""

import pytest
import warnings
from beancount_gocardless.importer import GoCardlessImporter
from beancount_gocardless.client import GoCardlessClient
from beancount_gocardless import GoCardLessClient, GoCardLessImporter
from beancount_gocardless.models import (
    Account,
    Balance,
    BookingStatus,
    Transaction,
    TransactionDirection,
)
from beancount_openbanking.providers.gocardless import GoCardlessProvider
from beancount_openbanking.providers.base import (
    Account as NewAccount,
    Balance as NewBalance,
    BookingStatus as NewBookingStatus,
    Transaction as NewTransaction,
    TransactionDirection as NewTransactionDirection,
)
from beancount_openbanking.config import GoCardlessConfig, ProviderName


from beancount_openbanking.importer import BankImporter as NewBankImporter


def test_shim_exports() -> None:
    """Verify that shim exports refer to the correct classes."""
    assert issubclass(GoCardlessImporter, NewBankImporter)
    assert GoCardlessClient is GoCardlessProvider
    assert GoCardLessImporter is GoCardlessImporter
    assert GoCardLessClient is GoCardlessClient
    assert Account is NewAccount
    assert Balance is NewBalance
    assert BookingStatus is NewBookingStatus
    assert Transaction is NewTransaction
    assert TransactionDirection is NewTransactionDirection


def test_shim_warnings(monkeypatch) -> None:
    """Verify that importing from shim triggers DeprecationWarning."""
    import importlib

    import beancount_gocardless

    monkeypatch.setenv("BEANCOUNT_OPENBANKING_SILENCE_RENAME_WARNING", "0")

    with warnings.catch_warnings():
        warnings.simplefilter("always", DeprecationWarning)
        with pytest.warns(
            DeprecationWarning,
            match="The package is currently published as 'beancount-gocardless'",
        ):
            importlib.reload(beancount_gocardless)


def test_shim_loads_legacy_config_without_provider(tmp_path) -> None:
    """Verify that the shim injects provider=gocardless for legacy configs."""
    config_file = tmp_path / "gocardless.yaml"
    config_file.write_text(
        """
secret_id: test-id
secret_key: test-key
accounts:
  - id: test-account
    asset_account: Assets:Banks:Test
""".strip()
    )

    importer = GoCardlessImporter(config_filepath=str(config_file))
    config = importer.load_config(str(config_file))

    assert isinstance(config, GoCardlessConfig)
    assert config.provider == ProviderName.GOCARDLESS
