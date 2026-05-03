"""Shared helpers for command-line interfaces."""

from __future__ import annotations

import argparse
from urllib.parse import urlparse

from rich.console import Console
from rich.table import Table

from .config import (
    EnableBankingConfig,
    GoCardlessConfig,
    ImportConfig,
    load_config,
)
from .providers import EnableBankingProvider, GoCardlessProvider

__all__ = [
    "DEFAULT_ENABLEBANKING_REDIRECT_URL",
    "DEFAULT_GOCARDLESS_REDIRECT_URL",
    "build_enablebanking_provider",
    "build_gocardless_provider",
    "default_callback_binding",
    "load_import_config",
    "render_table",
]

DEFAULT_GOCARDLESS_REDIRECT_URL = "http://localhost"
DEFAULT_ENABLEBANKING_REDIRECT_URL = "http://127.0.0.1:8765/callback"


def load_import_config(filepath: str, env_files: list[str]) -> ImportConfig:
    """Load a provider config from YAML."""

    return load_config(filepath, env_files=env_files)


def default_callback_binding(redirect_url: str) -> tuple[str, int]:
    """Return the local address for the OAuth callback server.

    The callback server always binds to a local address, even when the
    redirect URL is a public endpoint (e.g. an ngrok tunnel).
    """

    parsed = urlparse(redirect_url)
    host = parsed.hostname
    # Only trust the redirect URL's host if it is localhost-like;
    # otherwise fall back to the local loopback interface.
    if host in ("localhost", "127.0.0.1", "::1"):
        return host, parsed.port or 8765
    return "127.0.0.1", 8765


def render_table(
    console: Console,
    title: str,
    columns: list[str],
    rows: list[list[str]],
    empty_message: str,
) -> None:
    """Render a rich table or a fallback empty message."""

    if not rows:
        console.print(empty_message)
        return

    table = Table(title=title)
    for column in columns:
        table.add_column(column)
    for row in rows:
        table.add_row(*row)
    console.print(table)


def build_gocardless_provider(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> GoCardlessProvider:
    """Build a GoCardless provider from CLI arguments."""

    if args.config:
        config = load_config(
            args.config,
            env_files=args.env_file,
            default_provider="gocardless",
        )
        if not isinstance(config, GoCardlessConfig):
            parser.error(f"{args.config} is not a GoCardless config file")
        return GoCardlessProvider(
            secret_id=config.secret_id,
            secret_key=config.secret_key,
            cache_options=config.cache_options or None,
        )

    if not args.secret_id or not args.secret_key:
        parser.error(
            "GoCardless credentials are required. Use --config or pass "
            "--secret-id and --secret-key."
        )

    return GoCardlessProvider(
        secret_id=args.secret_id,
        secret_key=args.secret_key,
    )


def build_enablebanking_provider(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> EnableBankingProvider:
    """Build an Enable Banking provider from CLI arguments."""

    if args.config:
        config = load_config(
            args.config,
            env_files=args.env_file,
            default_provider="enablebanking",
        )
        if not isinstance(config, EnableBankingConfig):
            parser.error(f"{args.config} is not an Enable Banking config file")
        return EnableBankingProvider(
            application_id=config.application_id,
            private_key_path=config.private_key_path,
            redirect_url=config.redirect_url,
            session_store_path=config.session_store_path,
        )

    if not args.application_id or not args.private_key_path:
        parser.error(
            "Enable Banking credentials are required. Use --config or pass "
            "--application-id and --private-key-path."
        )

    return EnableBankingProvider(
        application_id=args.application_id,
        private_key_path=args.private_key_path,
        redirect_url=args.redirect_url,
        session_store_path=args.session_store_path,
    )
