"""Dedicated GoCardless CLI with an optional interactive flow."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

import questionary

from .cli_operations import GoCardlessOperations
from .cli_support import (
    DEFAULT_GOCARDLESS_REDIRECT_URL,
    build_gocardless_provider,
)
from .providers import Institution

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

__all__ = ["GoCardlessCLI", "build_parser", "main"]


class GoCardlessCLI(GoCardlessOperations):
    """Small GoCardless-only CLI with a questionary front-end."""

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

        institutions = self.provider.list_institutions(country=country)
        if not institutions:
            self.console.print(f"No banks found for {country}.")
            return

        institution = self._prompt_institution(institutions)
        if institution is None:
            return

        reference = questionary.text("Reference:").ask()
        if not reference or not reference.strip():
            return

        redirect_url = questionary.text(
            "Redirect URL:",
            default=DEFAULT_GOCARDLESS_REDIRECT_URL,
        ).ask()
        if not redirect_url or not redirect_url.strip():
            return

        self.create_link(
            institution_id=institution.id,
            reference=reference.strip(),
            redirect_url=redirect_url.strip(),
        )

    def delete_link_interactive(self) -> None:
        requisitions = self.provider.list_requisitions()
        if not requisitions:
            self.console.print("No bank links to delete.")
            return

        req_map = {
            f"{r.reference} — {r.institution_id} ({r.id})": r for r in requisitions
        }
        selection = questionary.select(
            "Select link to delete:",
            choices=[*req_map, "Back"],
        ).ask()
        if selection in {None, "Back"}:
            return

        requisition = req_map.get(selection)
        if requisition is None:
            return

        confirm = questionary.confirm(f"Delete requisition {requisition.id}?").ask()
        if confirm:
            self.delete_link(requisition_id=requisition.id)

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

    def _prompt_institution(
        self,
        institutions: Sequence[Institution],
    ) -> Institution | None:
        institution_map = {
            self.format_institution_choice(institution): institution
            for institution in institutions
        }
        selection = questionary.autocomplete(
            "Bank:",
            choices=[*institution_map, "Back"],
            ignore_case=True,
        ).ask()
        if selection in {None, "Back"}:
            return None
        return institution_map.get(selection)


def build_parser() -> argparse.ArgumentParser:
    """Build the GoCardless-only CLI parser."""

    parser = argparse.ArgumentParser(description="Dedicated GoCardless CLI")
    parser.add_argument("--config", help="Path to a GoCardless YAML config")
    parser.add_argument(
        "--env-file",
        action="append",
        default=[],
        help="Additional .env file loaded before expanding --config",
    )
    parser.add_argument(
        "--secret-id",
        default=os.getenv("GOCARDLESS_SECRET_ID"),
        help="GoCardless secret ID",
    )
    parser.add_argument(
        "--secret-key",
        default=os.getenv("GOCARDLESS_SECRET_KEY"),
        help="GoCardless secret key",
    )

    commands = parser.add_subparsers(dest="command")
    banks = commands.add_parser("banks", help="List banks")
    banks.add_argument("--country", help="Two-letter country code")
    banks.add_argument("--search", help="Filter by name, institution ID, or BIC")
    banks.set_defaults(command="banks")

    links = commands.add_parser("links", help="List bank links")
    links.set_defaults(command="links")

    delete_link = commands.add_parser("delete-link", help="Delete a bank link")
    delete_link.add_argument("--requisition-id", help="Requisition ID to delete")
    delete_link.set_defaults(command="delete-link")

    create_link = commands.add_parser("create-link", help="Create a bank link")
    create_link.add_argument("--institution-id", help="Institution ID")
    create_link.add_argument("--reference", help="Reference for the new link")
    create_link.add_argument(
        "--redirect-url",
        default=os.getenv("GOCARDLESS_REDIRECT_URL", DEFAULT_GOCARDLESS_REDIRECT_URL),
    )
    create_link.add_argument("--user-language")
    create_link.set_defaults(command="create-link")

    accounts = commands.add_parser("accounts", help="List linked accounts")
    accounts.set_defaults(command="accounts")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the dedicated GoCardless CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    cli = GoCardlessCLI(build_gocardless_provider(args, parser))

    if not args.command:
        if not sys.stdin.isatty():
            parser.print_help()
            return 1
        return cli.run_interactive()

    if args.command == "banks":
        cli.list_banks(country=args.country, search=args.search)
        return 0
    if args.command == "links":
        cli.list_links()
        return 0
    if args.command == "delete-link":
        if not args.requisition_id and sys.stdin.isatty():
            cli.delete_link_interactive()
            return 0
        if not args.requisition_id:
            parser.error("--requisition-id is required for delete-link")
        cli.delete_link(requisition_id=args.requisition_id)
        return 0
    if args.command == "accounts":
        cli.list_accounts()
        return 0
    if args.command == "create-link":
        if (not args.institution_id or not args.reference) and sys.stdin.isatty():
            cli.create_link_interactive()
            return 0
        if not args.institution_id or not args.reference:
            parser.error(
                "--institution-id and --reference are required for create-link"
            )
        cli.create_link(
            institution_id=args.institution_id,
            reference=args.reference,
            redirect_url=args.redirect_url,
            user_language=args.user_language,
        )
        return 0

    parser.print_help()
    return 1
