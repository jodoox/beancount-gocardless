"""Primary CLI for creating bank links and inspecting provider state."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .cli_operations import EB_DISPATCH, GC_DISPATCH, EnableBankingOperations, GoCardlessOperations
from .cli_support import (
    build_enablebanking_provider,
    build_gocardless_provider,
    run_command,
)
from .enablebanking_cli import EnableBankingCLI
from .gocardless_cli import GoCardlessCLI

__all__ = ["build_parser", "main"]


def _run_gocardless(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    provider = build_gocardless_provider(args, parser)
    result = run_command(
        GoCardlessOperations(provider), args, GC_DISPATCH, provider
    )
    if result is not None:
        return result
    if sys.stdin.isatty():
        return GoCardlessCLI(provider).run_interactive()
    parser.print_help()
    return 1


def _run_enablebanking(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    provider = build_enablebanking_provider(args, parser)
    result = run_command(
        EnableBankingOperations(provider), args, EB_DISPATCH, provider
    )
    if result is not None:
        return result
    if sys.stdin.isatty():
        return EnableBankingCLI(provider).run_interactive()
    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""

    from .cli_registry import (
        EB_CLI_MULTI,
        GC_CLI_MULTI,
        build_multiprovider_parser,
    )

    return build_multiprovider_parser(
        GC_CLI_MULTI,
        EB_CLI_MULTI,
        description="Open banking CLI for bank link creation and provider inspection",
    )


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
