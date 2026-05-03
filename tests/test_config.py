"""Tests for configuration loading."""

from __future__ import annotations

from beancount_openbanking.config import (
    EnableBankingConfig,
    GoCardlessConfig,
    ProviderName,
    load_config,
)
from beancount_openbanking.importer import BankImporter


class TestConfigLoading:
    def test_load_gocardless_config(self, tmp_path) -> None:
        config_file = tmp_path / "gocardless.yaml"
        config_file.write_text(
            """
provider: gocardless
secret_id: test-id
secret_key: test-key
accounts:
  - id: test-account
    asset_account: Assets:Banks:Test
""".strip()
        )

        config = BankImporter().load_config(str(config_file))

        assert isinstance(config, GoCardlessConfig)
        assert config.provider == ProviderName.GOCARDLESS

    def test_load_enablebanking_config(self, tmp_path) -> None:
        config_file = tmp_path / "enablebanking.yaml"
        config_file.write_text(
            """
provider: enablebanking
application_id: test-app-id
private_key_path: /path/to/key.pem
accounts:
  - id: test-account
    asset_account: Assets:Banks:Test
""".strip()
        )

        config = BankImporter().load_config(str(config_file))

        assert isinstance(config, EnableBankingConfig)
        assert config.provider == ProviderName.ENABLEBANKING

    def test_load_config_expands_nearest_dotenv(self, tmp_path) -> None:
        (tmp_path / ".env").write_text(
            "GOCARDLESS_SECRET_ID=from-dotenv\nGOCARDLESS_SECRET_KEY=dotenv-key\n"
        )
        config_file = tmp_path / "gocardless.yaml"
        config_file.write_text(
            """
provider: gocardless
secret_id: $GOCARDLESS_SECRET_ID
secret_key: $GOCARDLESS_SECRET_KEY
accounts:
  - id: test-account
    asset_account: Assets:Banks:Test
""".strip()
        )

        config = BankImporter().load_config(str(config_file))

        assert isinstance(config, GoCardlessConfig)
        assert config.secret_id == "from-dotenv"
        assert config.secret_key == "dotenv-key"

    def test_load_config_expands_env_files_and_inline_env(self, tmp_path) -> None:
        env_file = tmp_path / "bank.env"
        env_file.write_text("SECRET_ID=file-id\n")
        config_file = tmp_path / "gocardless.yaml"
        config_file.write_text(
            """
provider: gocardless
env_files:
  - bank.env
env:
  SECRET_KEY: inline-key
secret_id: $SECRET_ID
secret_key: $SECRET_KEY
accounts:
  - id: test-account
    asset_account: Assets:Banks:Test
""".strip()
        )

        config = BankImporter().load_config(str(config_file))

        assert isinstance(config, GoCardlessConfig)
        assert config.secret_id == "file-id"
        assert config.secret_key == "inline-key"

    def test_load_config_resolves_enablebanking_paths_relative_to_yaml(
        self,
        tmp_path,
    ) -> None:
        key_path = tmp_path / "keys" / "enablebanking.pem"
        session_store_path = tmp_path / ".secrets" / "sessions"
        config_file = tmp_path / "configs" / "enablebanking.yaml"
        config_file.parent.mkdir()
        config_file.write_text(
            """
provider: enablebanking
application_id: test-app-id
private_key_path: ../keys/enablebanking.pem
session_store_path: ../.secrets/sessions
accounts:
  - id: test-account
    asset_account: Assets:Banks:Test
""".strip()
        )

        config = BankImporter().load_config(str(config_file))

        assert isinstance(config, EnableBankingConfig)
        assert config.private_key_path == str(key_path.resolve())
        assert config.session_store_path == str(session_store_path.resolve())

    def test_load_config_can_infer_provider_for_provider_specific_entrypoints(
        self,
        tmp_path,
    ) -> None:
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

        config = load_config(str(config_file), default_provider="gocardless")

        assert isinstance(config, GoCardlessConfig)
        assert config.provider == ProviderName.GOCARDLESS

    def test_identify_uses_config_filepath(self, tmp_path) -> None:
        config_file = tmp_path / "openbanking.yml"
        config_file.write_text(
            """
provider: gocardless
secret_id: test-id
secret_key: test-key
accounts:
  - id: test-account
    asset_account: Assets:Banks:Test
""".strip()
        )

        default_importer = BankImporter()
        importer = BankImporter(config_filepath=str(config_file))

        assert default_importer.config_filepath.name == "openbanking.yml"
        assert importer.config_filepath.name == "openbanking.yml"
        assert importer.identify(str(config_file)) is True
        assert importer.identify(str(tmp_path / "other.yml")) is False
