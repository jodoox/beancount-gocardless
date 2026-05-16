"""Dedicated GoCardless CLI with an optional interactive flow."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

import questionary

from .cli_operations import GoCardlessOperations
from .cli_support import (
    DEFAULT_GOCARDLESS_REDIRECT_URL,
    BaseInteractiveCLI,
    build_gocardless_provider,
)
from .providers import Institution

__all__ = ["GoCardlessCLI", "build_parser", "main"]


class GoCardlessCLI(BaseInteractiveCLI, GoCardlessOperations):
    """Small GoCardless-only CLI with a questionary front-end."""

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

    from .cli_registry import GC_CLI_DEDICATED, build_provider_parser

    return build_provider_parser(GC_CLI_DEDICATED)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the dedicated GoCardless CLI."""

    from .cli_operations import GC_DISPATCH
    from .cli_support import run_command

    parser = build_parser()
    args = parser.parse_args(argv)
    provider = build_gocardless_provider(args, parser)
    cli = GoCardlessCLI(provider)

    if not args.command:
        if not sys.stdin.isatty():
            parser.print_help()
            return 1
        return cli.run_interactive()

    if args.command == "delete-link" and not args.requisition_id and sys.stdin.isatty():
        cli.delete_link_interactive()
        return 0
    if args.command == "create-link" and (not args.institution_id or not args.reference) and sys.stdin.isatty():
        cli.create_link_interactive()
        return 0

    result = run_command(cli, args, GC_DISPATCH, provider)
    if result is not None:
        return result
    parser.print_help()
    return 1
