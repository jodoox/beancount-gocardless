"""Tests for the CLI entry points."""

from __future__ import annotations

import os
import shutil
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from beancount_openbanking.providers import (
    EnableBankingAspsp,
    EnableBankingSession,
    GoCardlessProvider,
    Requisition,
)


class TestCLI:
    def test_installed_primary_cli_entry_point(self) -> None:
        executable = shutil.which("beancount-openbanking")
        assert executable is not None
        env = {**os.environ, "BEANCOUNT_OPENBANKING_SILENCE_RENAME_WARNING": "0"}

        result = subprocess.run(
            [executable, "--help"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

        assert result.returncode == 0
        assert "Open banking CLI for bank link creation and provider inspection" in (
            result.stdout
        )
        assert "rename to 'beancount-openbanking' is planned" in result.stderr

    def test_installed_gocardless_cli_entry_point(self) -> None:
        executable = shutil.which("beancount-gocardless")
        assert executable is not None
        env = {**os.environ, "BEANCOUNT_OPENBANKING_SILENCE_RENAME_WARNING": "0"}

        result = subprocess.run(
            [executable, "--help"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

        assert result.returncode == 0
        assert "Dedicated GoCardless CLI" in result.stdout
        assert "rename to 'beancount-openbanking' is planned" in result.stderr

    def test_main_without_subcommand_in_non_interactive_mode(self, capsys) -> None:
        cli_module = pytest.importorskip("beancount_openbanking.cli")
        exit_code = cli_module.main([])

        captured = capsys.readouterr()
        assert exit_code == 1
        assert (
            "Open banking CLI for bank link creation and provider inspection"
            in captured.out
        )

    def test_gocardless_links_command(self, capsys) -> None:
        cli_module = pytest.importorskip("beancount_openbanking.cli")
        provider = MagicMock(spec=GoCardlessProvider)
        provider.list_requisitions.return_value = [
            Requisition(
                id="req-1",
                created="2024-01-01T12:00:00Z",
                redirect="http://localhost",
                status="LN",
                institution_id="REVOLUT_REVOGB21",
                reference="revolut",
                accounts=["acc-1"],
                link="https://example.com/auth",
            )
        ]

        with patch(
            "beancount_openbanking.cli.build_gocardless_provider",
            return_value=provider,
        ):
            exit_code = cli_module.main(
                [
                    "gocardless",
                    "--secret-id",
                    "test-id",
                    "--secret-key",
                    "test-key",
                    "links",
                ]
            )

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "revolut" in captured.out

    def test_dedicated_gocardless_cli_without_subcommand(self, capsys) -> None:
        cli_module = pytest.importorskip("beancount_openbanking.gocardless_cli")
        with (
            patch(
                "beancount_openbanking.gocardless_cli.sys.stdin.isatty",
                return_value=False,
            ),
            patch(
                "beancount_openbanking.gocardless_cli.build_gocardless_provider",
            ),
        ):
            exit_code = cli_module.main(
                ["--secret-id", "test-id", "--secret-key", "test-key"]
            )

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Dedicated GoCardless CLI" in captured.out

    def test_dedicated_gocardless_links_command(self, capsys) -> None:
        cli_module = pytest.importorskip("beancount_openbanking.gocardless_cli")
        provider = MagicMock(spec=GoCardlessProvider)
        provider.list_requisitions.return_value = [
            Requisition(
                id="req-1",
                created="2024-01-01T12:00:00Z",
                redirect="http://localhost",
                status="LN",
                institution_id="REVOLUT_REVOGB21",
                reference="revolut",
                accounts=["acc-1"],
                link="https://example.com/auth",
            )
        ]

        with patch(
            "beancount_openbanking.gocardless_cli.build_gocardless_provider",
            return_value=provider,
        ):
            exit_code = cli_module.main(
                [
                    "--secret-id",
                    "test-id",
                    "--secret-key",
                    "test-key",
                    "links",
                ]
            )

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "revolut" in captured.out

    def test_dedicated_gocardless_config_infers_provider(self, tmp_path) -> None:
        cli_module = pytest.importorskip("beancount_openbanking.gocardless_cli")
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

        captured: dict[str, object] = {}

        def fake_list_links(self) -> None:
            captured["provider_name"] = self.provider.secret_id

        with patch.object(
            cli_module.GoCardlessOperations,
            "list_links",
            fake_list_links,
        ):
            exit_code = cli_module.main(["--config", str(config_file), "links"])

        assert exit_code == 0
        assert captured["provider_name"] == "test-id"

    def test_installed_enablebanking_cli_entry_point(self) -> None:
        executable = shutil.which("beancount-enablebanking")
        assert executable is not None
        env = {**os.environ, "BEANCOUNT_OPENBANKING_SILENCE_RENAME_WARNING": "0"}

        result = subprocess.run(
            [executable, "--help"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

        assert result.returncode == 0
        assert "Dedicated Enable Banking CLI" in result.stdout
        assert "rename to 'beancount-openbanking' is planned" in result.stderr

    def test_enablebanking_links_command(self, capsys) -> None:
        cli_module = pytest.importorskip("beancount_openbanking.cli")
        provider = MagicMock()
        provider.list_sessions.return_value = [
            EnableBankingSession(
                session_id="sess-1",
                aspsp=EnableBankingAspsp(name="Revolut", country="FR"),
                accounts=["acc-1"],
                status="AUTHORIZED",
                authorized="2024-01-01T12:00:00Z",
            )
        ]

        with patch(
            "beancount_openbanking.cli.build_enablebanking_provider",
            return_value=provider,
        ):
            exit_code = cli_module.main(
                [
                    "enablebanking",
                    "--application-id",
                    "test-app",
                    "--private-key-path",
                    "/path/to/key.pem",
                    "links",
                ]
            )

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "Revolut" in captured.out

    def test_dedicated_enablebanking_cli_without_subcommand(self, capsys) -> None:
        cli_module = pytest.importorskip("beancount_openbanking.enablebanking_cli")
        with (
            patch(
                "beancount_openbanking.enablebanking_cli.sys.stdin.isatty",
                return_value=False,
            ),
            patch(
                "beancount_openbanking.enablebanking_cli.build_enablebanking_provider",
            ),
        ):
            exit_code = cli_module.main(
                [
                    "--application-id",
                    "test-app",
                    "--private-key-path",
                    "/path/to/key.pem",
                ]
            )

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Dedicated Enable Banking CLI" in captured.out

    def test_dedicated_enablebanking_links_command(self, capsys) -> None:
        cli_module = pytest.importorskip("beancount_openbanking.enablebanking_cli")
        provider = MagicMock()
        provider.list_sessions.return_value = [
            EnableBankingSession(
                session_id="sess-1",
                aspsp=EnableBankingAspsp(name="Hello Bank", country="FR"),
                accounts=["acc-1"],
                status="AUTHORIZED",
                authorized="2024-01-01T12:00:00Z",
            )
        ]

        with patch(
            "beancount_openbanking.enablebanking_cli.build_enablebanking_provider",
            return_value=provider,
        ):
            exit_code = cli_module.main(
                [
                    "--application-id",
                    "test-app",
                    "--private-key-path",
                    "/path/to/key.pem",
                    "links",
                ]
            )

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "Hello Bank" in captured.out

    def test_enablebanking_interactive_create_link_updates_redirect_url(self) -> None:
        cli_module = pytest.importorskip("beancount_openbanking.enablebanking_cli")
        provider = MagicMock()
        provider.redirect_url = "http://127.0.0.1:8765/callback"
        cli = cli_module.EnableBankingCLI(provider)

        with (
            patch.object(cli, "_prompt_country", return_value="FR"),
            patch.object(
                cli,
                "_prompt_aspsp",
                return_value={"name": "BNP Paribas", "bic": "BNPAFRPP"},
            ),
            patch.object(
                provider,
                "list_aspsps",
                return_value=[{"name": "BNP Paribas", "bic": "BNPAFRPP"}],
            ),
            patch(
                "beancount_openbanking.enablebanking_cli.questionary.select"
            ) as mock_select,
            patch(
                "beancount_openbanking.enablebanking_cli.questionary.text"
            ) as mock_text,
            patch.object(cli, "create_link") as mock_create_link,
        ):
            mock_select.return_value.ask.return_value = "personal"
            mock_text.side_effect = [
                MagicMock(ask=MagicMock(return_value="90")),
                MagicMock(
                    ask=MagicMock(return_value="http://localhost:9999/custom-callback")
                ),
            ]

            cli.create_link_interactive()

        assert provider.redirect_url == "http://localhost:9999/custom-callback"
        mock_create_link.assert_called_once_with(
            aspsp_name="BNP Paribas",
            aspsp_country="FR",
            callback_host="localhost",
            callback_port=9999,
            psu_type="personal",
            access_days=90,
            open_browser=True,
        )

    def test_enablebanking_interactive_delete_link_uses_session_model(self) -> None:
        cli_module = pytest.importorskip("beancount_openbanking.enablebanking_cli")
        provider = MagicMock()
        provider.list_sessions.return_value = [
            EnableBankingSession(
                session_id="sess-1",
                aspsp=EnableBankingAspsp(name="Hello Bank", country="FR"),
                accounts=["acc-1"],
            )
        ]
        cli = cli_module.EnableBankingCLI(provider)

        with (
            patch(
                "beancount_openbanking.enablebanking_cli.questionary.select"
            ) as mock_select,
            patch(
                "beancount_openbanking.enablebanking_cli.questionary.confirm"
            ) as mock_confirm,
            patch.object(cli, "delete_link") as mock_delete_link,
        ):
            mock_select.return_value.ask.return_value = "Hello Bank - sess-1"
            mock_confirm.return_value.ask.return_value = True

            cli.delete_link_interactive()

        mock_delete_link.assert_called_once_with(session_id="sess-1")
