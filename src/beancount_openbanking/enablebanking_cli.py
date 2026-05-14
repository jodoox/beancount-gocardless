"""Dedicated Enable Banking CLI with an optional interactive flow."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

import questionary

from .cli_operations import EnableBankingOperations
from .cli_support import (
    DEFAULT_ENABLEBANKING_REDIRECT_URL,
    build_enablebanking_provider,
    default_callback_binding,
)

COMMON_COUNTRIES = [
    "AT",
    "BE",
    "DE",
    "ES",
    "FR",
    "GB",
    "IE",
    "IT",
    "NL",
    "PT",
]

__all__ = ["EnableBankingCLI", "build_parser", "main"]


class EnableBankingCLI(EnableBankingOperations):
    """Small Enable Banking-only CLI with a questionary front-end."""

    def run_interactive(self) -> int:
        while True:
            action = questionary.select(
                "What do you want to do?",
                choices=[
                    "List linked accounts",
                    "Browse banks",
                    "List bank links",
                    "Create bank link",
                    "Delete bank link",
                    "Exit",
                ],
            ).ask()

            if action in {None, "Exit"}:
                return 0
            if action == "List linked accounts":
                self.list_accounts()
                continue
            if action == "Browse banks":
                country = self._prompt_country()
                if country:
                    self.list_banks(country=country)
                continue
            if action == "List bank links":
                self.list_links()
                continue
            if action == "Create bank link":
                self.create_link_interactive()
                continue
            if action == "Delete bank link":
                self.delete_link_interactive()

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

        session_map = {
            (
                f"{s.aspsp.name if s.aspsp and s.aspsp.name else 'Unknown'}"
                f" - {s.session_id or ''}"
            ): s
            for s in sessions
        }
        selection = questionary.select(
            "Select link to delete:",
            choices=[*session_map, "Back"],
        ).ask()
        if selection in {None, "Back"}:
            return

        session = session_map.get(selection)
        if session is None:
            return

        session_id = session.session_id or ""
        confirm = questionary.confirm(f"Delete session {session_id}?").ask()
        if confirm:
            self.delete_link(session_id=session_id)

    def _prompt_country(self) -> str | None:
        choice = questionary.select(
            "Country:",
            choices=[*COMMON_COUNTRIES, "Other", "Back"],
        ).ask()
        if choice in {None, "Back"}:
            return None
        if choice == "Other":
            country = questionary.text("Two-letter country code:").ask()
            if not country or not country.strip():
                return None
            return country.strip().upper()
        return choice

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
    if args.command == "create-link" and (not args.country or not args.aspsp_name) and sys.stdin.isatty():
        cli.create_link_interactive()
        return 0

    result = run_command(cli, args, EB_DISPATCH, provider)
    if result is not None:
        return result
    parser.print_help()
    return 1
