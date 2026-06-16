"""Dedicated Enable Banking CLI with an optional interactive flow."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

import questionary

from .cli_factory import build_provider
from .cli_operations import (
    EnableBankingOperations,
)
from .cli_support import (
    DEFAULT_ENABLEBANKING_REDIRECT_URL,
    BaseInteractiveCLI,
    default_callback_binding,
)
from .config import EnableBankingConfig
from .providers import EnableBankingProvider

__all__ = ["EnableBankingCLI", "build_enablebanking_provider", "build_parser", "main"]


class EnableBankingCLI(BaseInteractiveCLI, EnableBankingOperations):
    """Small Enable Banking-only CLI with a questionary front-end."""

    def create_link_interactive(self) -> None:
        country = self._prompt_country()
        if country is None:
            return

        banks = self.provider.list_aspsps(country=country)
        if not banks:
            self.console.print(f"No banks found for {country}.")
            return

        aspsp = self._prompt_aspsp(banks)
        if aspsp is None:
            return

        psu_type = questionary.select(
            "PSU type:",
            choices=["personal", "business"],
            default="personal",
        ).ask()
        if psu_type is None:
            return

        access_days = questionary.text(
            "Access validity (days):",
            default="90",
            validate=lambda text: text.isdigit() or "Must be a number",
        ).ask()
        if not access_days:
            return

        redirect_url = questionary.text(
            "Redirect URL:",
            default=self.provider.redirect_url or DEFAULT_ENABLEBANKING_REDIRECT_URL,
        ).ask()
        if not redirect_url or not redirect_url.strip():
            return
        self.provider.redirect_url = redirect_url.strip()

        callback_host, callback_port = default_callback_binding(
            self.provider.redirect_url
        )

        self.console.print(
            f"Starting authorization with {aspsp['name']} ({country})..."
        )
        self.create_link(
            aspsp_name=aspsp["name"],
            aspsp_country=country,
            callback_host=callback_host,
            callback_port=callback_port,
            psu_type=psu_type,
            access_days=int(access_days),
            open_browser=True,
        )

    def delete_link_interactive(self) -> None:
        sessions = self.provider.list_sessions()
        if not sessions:
            self.console.print("No bank links to delete.")
            return

        from .auth.enablebanking_types import EnableBankingSession
        from .cli_support import prompt_pick

        def format_session(s: EnableBankingSession) -> str:
            aspsp_name = s.aspsp.name if s.aspsp and s.aspsp.name else "Unknown"
            return f"{aspsp_name} - {s.session_id or ''}"

        picked = prompt_pick(
            self.console,
            sessions,
            format_fn=format_session,
            question="Select link to delete:",
            confirm_template="Delete session {item.session_id}?",
        )
        if picked is None:
            return
        self.delete_link(session_id=picked.session_id or "")

    def _prompt_aspsp(self, banks: list[dict]) -> dict | None:
        bank_map = {
            f"{bank.get('name', 'Unknown')} ({bank.get('bic', 'N/A')})": bank
            for bank in banks
        }
        selection = questionary.autocomplete(
            "Bank:",
            choices=[*bank_map, "Back"],
            ignore_case=True,
        ).ask()
        if selection in {None, "Back"}:
            return None
        return bank_map.get(selection)


def build_enablebanking_provider(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> EnableBankingProvider:
    """Build an Enable Banking provider from CLI arguments or a config file."""
    return build_provider(
        args,
        parser,
        provider_name="enablebanking",
        config_class=EnableBankingConfig,
        provider_class=EnableBankingProvider,
        config_label="Enable Banking",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the Enable Banking-only CLI parser."""

    from .cli_registry import EB_CLI_DEDICATED, build_provider_parser

    return build_provider_parser(EB_CLI_DEDICATED)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the dedicated Enable Banking CLI."""

    from .cli_operations import EB_DISPATCH
    from .cli_support import run_command

    parser = build_parser()
    args = parser.parse_args(argv)
    provider = build_enablebanking_provider(args, parser)
    cli = EnableBankingCLI(provider)

    if not args.command:
        if not sys.stdin.isatty():
            parser.print_help()
            return 1
        return cli.run_interactive()

    if args.command == "delete-link" and not args.session_id and sys.stdin.isatty():
        cli.delete_link_interactive()
        return 0
    if (
        args.command == "create-link"
        and (not args.country or not args.aspsp_name)
        and sys.stdin.isatty()
    ):
        cli.create_link_interactive()
        return 0

    result = run_command(cli, args, EB_DISPATCH, provider)
    if result is not None:
        return result
    parser.print_help()
    return 1
