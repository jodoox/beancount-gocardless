"""Shared CLI helpers: interactive mixin, table rendering, dispatch.

Lives apart from ``cli_operations.py`` so that ``*Operations`` classes are
free of presentation and dispatch concerns. Used by both the dedicated
``beancount-{gocardless,enablebanking}`` CLIs and the multi-provider
``beancount-openbanking`` CLI.
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Any, Callable, Protocol, TypeVar
from urllib.parse import urlparse

import questionary
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from .providers.base import Provider

__all__ = [
    "COMMON_COUNTRIES",
    "DEFAULT_ENABLEBANKING_REDIRECT_URL",
    "DEFAULT_GOCARDLESS_REDIRECT_URL",
    "DispatchFn",
    "DispatchMap",
    "default_callback_binding",
    "prompt_pick",
    "render_table",
    "run_command",
]


COMMON_COUNTRIES: list[str] = [
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

DEFAULT_GOCARDLESS_REDIRECT_URL = "http://localhost"
DEFAULT_ENABLEBANKING_REDIRECT_URL = "http://127.0.0.1:8765/callback"

DispatchFn = Callable[[Any, argparse.Namespace, "Provider"], None]
DispatchMap = dict[str, DispatchFn]

T = TypeVar("T")


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


def default_callback_binding(redirect_url: str) -> tuple[str, int]:
    """Return the local address for the OAuth callback server.

    The callback server always binds to a local address, even when the
    redirect URL is a public endpoint (e.g. an ngrok tunnel).
    """
    parsed = urlparse(redirect_url)
    host = parsed.hostname
    if host in ("localhost", "127.0.0.1", "::1"):
        return host, parsed.port or 8765
    return "127.0.0.1", 8765


def prompt_pick(
    console: Console,
    items: list[T],
    format_fn: Callable[[T], str],
    question: str,
    confirm_template: str,
) -> T | None:
    """Ask the user to pick one of ``items`` and confirm a destructive action.

    ``format_fn`` produces the label shown in the select prompt.
    ``confirm_template`` is an ``str.format`` template; the picked item is
    passed as ``item`` for the user-visible message. Returns the picked
    item, or ``None`` if the user backed out or declined the confirm.
    """
    if not items:
        console.print("Nothing to choose from.")
        return None

    item_map = {format_fn(item): item for item in items}
    selection = questionary.select(
        question,
        choices=[*item_map, "Back"],
    ).ask()
    if selection in {None, "Back"}:
        return None

    item = item_map.get(selection)
    if item is None:
        return None

    if not questionary.confirm(confirm_template.format(item=item)).ask():
        return None
    return item


def run_command(
    ops: Any,
    args: argparse.Namespace,
    dispatch_map: DispatchMap,
    provider: "Provider",
) -> int | None:
    """Execute a CLI command from a dispatch map.

    Returns ``0`` on success, or ``None`` if the command was not found in the
    dispatch map (so the caller can fall back to help / interactive mode).
    """
    handler = dispatch_map.get(args.command)
    if handler is None:
        return None
    handler(ops, args, provider)
    return 0


class _InteractiveSubclass(Protocol):
    """Surface a ``BaseInteractiveCLI`` subclass must provide.

    The list/operations methods come from the ``*Operations`` base class; the
    ``*_interactive`` methods are defined by the subclass itself; ``console``
    comes from either base.
    """

    def list_accounts(self) -> object: ...
    def list_banks(self, country: str | None = ...) -> object: ...
    def list_links(self) -> object: ...
    def create_link_interactive(self) -> object: ...
    def delete_link_interactive(self) -> object: ...
    def _prompt_country(self) -> str | None: ...
    def console(self) -> object: ...


class BaseInteractiveCLI:
    """Mixin providing the interactive menu loop and shared prompts.

    Subclasses must inherit alongside a ``*Operations`` class (which provides
    ``list_accounts``, ``list_banks``, ``list_links``) and must define
    ``create_link_interactive`` and ``delete_link_interactive`` themselves.
    They must also expose a ``console`` attribute for output.
    """

    def create_link_interactive(self) -> None:
        raise NotImplementedError

    def delete_link_interactive(self) -> None:
        raise NotImplementedError

    def run_interactive(self) -> int:
        from typing import cast

        typed = cast(_InteractiveSubclass, self)
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
                typed.list_accounts()
            elif action == "Browse banks":
                country = typed._prompt_country()
                if country:
                    typed.list_banks(country=country)
            elif action == "List bank links":
                typed.list_links()
            elif action == "Create bank link":
                typed.create_link_interactive()
            elif action == "Delete bank link":
                typed.delete_link_interactive()

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
