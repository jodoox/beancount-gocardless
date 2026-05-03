"""Primary CLI for creating bank links and inspecting provider state."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

from .cli_operations import EnableBankingOperations, GoCardlessOperations
from .cli_support import (
    DEFAULT_ENABLEBANKING_REDIRECT_URL,
    DEFAULT_GOCARDLESS_REDIRECT_URL,
    build_enablebanking_provider,
    build_gocardless_provider,
    default_callback_binding,
)
from .enablebanking_cli import EnableBankingCLI
from .gocardless_cli import GoCardlessCLI

__all__ = ["build_parser", "main"]


def _run_gocardless(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    provider = build_gocardless_provider(args, parser)

    if args.command == "banks":
        GoCardlessOperations(provider).list_banks(
            country=args.country, search=args.search
        )
        return 0

    if args.command == "links":
        GoCardlessOperations(provider).list_links()
        return 0

    if args.command == "delete-link":
        GoCardlessOperations(provider).delete_link(requisition_id=args.requisition_id)
        return 0

    if args.command == "create-link":
        GoCardlessOperations(provider).create_link(
            institution_id=args.institution_id,
            reference=args.reference,
            redirect_url=args.redirect_url,
            user_language=args.user_language,
        )
        return 0

    if args.command == "accounts":
        GoCardlessOperations(provider).list_accounts()
        return 0

    if sys.stdin.isatty():
        return GoCardlessCLI(provider).run_interactive()

    parser.print_help()
    return 1


def _run_enablebanking(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    provider = build_enablebanking_provider(args, parser)

    if args.command == "banks":
        EnableBankingOperations(provider).list_banks(args.country, search=args.search)
        return 0

    if args.command == "links":
        EnableBankingOperations(provider).list_links()
        return 0

    if args.command == "delete-link":
        EnableBankingOperations(provider).delete_link(session_id=args.session_id)
        return 0

    if args.command == "create-link":
        callback_host, callback_port = default_callback_binding(provider.redirect_url)
        EnableBankingOperations(provider).create_link(
            aspsp_name=args.aspsp_name,
            aspsp_country=args.country,
            callback_host=args.callback_host or callback_host,
            callback_port=args.callback_port or callback_port,
            psu_type=args.psu_type,
            access_days=args.access_days,
            open_browser=not args.no_browser,
        )
        return 0

    if args.command == "accounts":
        EnableBankingOperations(provider).list_accounts()
        return 0

    if sys.stdin.isatty():
        return EnableBankingCLI(provider).run_interactive()

    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(
        description="Open banking CLI for bank link creation and provider inspection"
    )
    providers = parser.add_subparsers(dest="provider_name")

    gocardless = providers.add_parser("gocardless", help="GoCardless tools")
    gocardless.add_argument("--config", help="Path to a GoCardless YAML config")
    gocardless.add_argument(
        "--env-file",
        action="append",
        default=[],
        help="Additional .env file loaded before expanding --config",
    )
    gocardless.add_argument(
        "--secret-id",
        default=os.getenv("GOCARDLESS_SECRET_ID"),
        help="GoCardless secret ID",
    )
    gocardless.add_argument(
        "--secret-key",
        default=os.getenv("GOCARDLESS_SECRET_KEY"),
        help="GoCardless secret key",
    )
    gocardless_commands = gocardless.add_subparsers(dest="command")
    gocardless_banks = gocardless_commands.add_parser("banks", help="List banks")
    gocardless_banks.add_argument("--country", help="Two-letter country code")
    gocardless_banks.add_argument(
        "--search", help="Filter by name, institution ID, or BIC"
    )
    gocardless_banks.set_defaults(command="banks")
    gocardless_links = gocardless_commands.add_parser("links", help="List bank links")
    gocardless_links.set_defaults(command="links")
    gocardless_delete_link = gocardless_commands.add_parser(
        "delete-link",
        help="Delete a bank link",
    )
    gocardless_delete_link.add_argument("--requisition-id", required=True)
    gocardless_delete_link.set_defaults(command="delete-link")
    gocardless_create_link = gocardless_commands.add_parser(
        "create-link",
        help="Create a bank link",
    )
    gocardless_create_link.add_argument("--institution-id", required=True)
    gocardless_create_link.add_argument("--reference", required=True)
    gocardless_create_link.add_argument(
        "--redirect-url",
        default=os.getenv("GOCARDLESS_REDIRECT_URL", DEFAULT_GOCARDLESS_REDIRECT_URL),
    )
    gocardless_create_link.add_argument("--user-language")
    gocardless_create_link.set_defaults(command="create-link")
    gocardless_accounts = gocardless_commands.add_parser(
        "accounts", help="List linked accounts"
    )
    gocardless_accounts.set_defaults(command="accounts")

    enablebanking = providers.add_parser("enablebanking", help="Enable Banking tools")
    enablebanking.add_argument("--config", help="Path to an Enable Banking YAML config")
    enablebanking.add_argument(
        "--env-file",
        action="append",
        default=[],
        help="Additional .env file loaded before expanding --config",
    )
    enablebanking.add_argument(
        "--application-id",
        default=os.getenv("ENABLE_BANKING_APPLICATION_ID"),
    )
    enablebanking.add_argument(
        "--private-key-path",
        default=os.getenv("ENABLE_BANKING_PRIVATE_KEY_PATH"),
    )
    enablebanking.add_argument(
        "--redirect-url",
        default=os.getenv(
            "ENABLE_BANKING_REDIRECT_URL", DEFAULT_ENABLEBANKING_REDIRECT_URL
        ),
    )
    enablebanking.add_argument(
        "--session-store-path",
        default=os.getenv("ENABLE_BANKING_SESSION_STORE_PATH"),
    )
    enablebanking_commands = enablebanking.add_subparsers(dest="command")
    enablebanking_banks = enablebanking_commands.add_parser("banks", help="List banks")
    enablebanking_banks.add_argument("--country", required=True)
    enablebanking_banks.add_argument("--search")
    enablebanking_banks.set_defaults(command="banks")
    enablebanking_links = enablebanking_commands.add_parser(
        "links", help="List bank links"
    )
    enablebanking_links.set_defaults(command="links")
    enablebanking_delete_link = enablebanking_commands.add_parser(
        "delete-link",
        help="Delete a bank link",
    )
    enablebanking_delete_link.add_argument("--session-id", required=True)
    enablebanking_delete_link.set_defaults(command="delete-link")
    enablebanking_create_link = enablebanking_commands.add_parser(
        "create-link",
        help="Create a bank link",
    )
    enablebanking_create_link.add_argument("--country", required=True)
    enablebanking_create_link.add_argument("--aspsp-name", required=True)
    enablebanking_create_link.add_argument(
        "--psu-type",
        default="personal",
        choices=["personal", "business"],
    )
    enablebanking_create_link.add_argument("--access-days", type=int, default=90)
    enablebanking_create_link.add_argument("--callback-host")
    enablebanking_create_link.add_argument("--callback-port", type=int)
    enablebanking_create_link.add_argument("--no-browser", action="store_true")
    enablebanking_create_link.set_defaults(command="create-link")
    enablebanking_accounts = enablebanking_commands.add_parser(
        "accounts",
        help="List linked accounts",
    )
    enablebanking_accounts.set_defaults(command="accounts")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.provider_name == "gocardless":
        return _run_gocardless(args, parser)
    if args.provider_name == "enablebanking":
        return _run_enablebanking(args, parser)

    parser.print_help()
    return 1
