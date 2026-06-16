"""CLI argument registry — single source of truth for argument definitions.

Provides data structures and builder functions so that the three CLI
entry points (:mod:`cli`, :mod:`gocardless_cli`, :mod:`enablebanking_cli`)
share one canonical set of argument definitions instead of triplicating them.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from typing import Any

from .cli_support import (
    DEFAULT_ENABLEBANKING_REDIRECT_URL,
    DEFAULT_GOCARDLESS_REDIRECT_URL,
)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Arg:
    """A single CLI argument or flag."""

    flags: list[str]
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandGroup:
    """A subcommand and its arguments."""

    name: str
    help: str
    args: list[Arg] = field(default_factory=list)


@dataclass
class ProviderCLIDef:
    """Complete CLI definition for one provider."""

    name: str
    help: str
    global_args: list[Arg] = field(default_factory=list)
    command_groups: list[CommandGroup] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Builder functions
# ---------------------------------------------------------------------------


def _add_args(parser: argparse.ArgumentParser, args: list[Arg]) -> None:
    for arg in args:
        parser.add_argument(*arg.flags, **arg.kwargs)


def build_provider_parser(defn: ProviderCLIDef) -> argparse.ArgumentParser:
    """Build a stand-alone parser for a single provider (dedicated CLI)."""
    parser = argparse.ArgumentParser(description=defn.help)
    _add_args(parser, defn.global_args)
    _add_command_subparsers(parser, defn.command_groups)
    return parser


def build_multiprovider_parser(
    gc_def: ProviderCLIDef,
    eb_def: ProviderCLIDef,
    description: str,
) -> argparse.ArgumentParser:
    """Build the multi-provider CLI parser (two subparsers, one per provider)."""
    parser = argparse.ArgumentParser(description=description)
    subparsers = parser.add_subparsers(dest="provider_name")
    for defn in [gc_def, eb_def]:
        sub = subparsers.add_parser(defn.name, help=defn.help)
        _add_args(sub, defn.global_args)
        _add_command_subparsers(sub, defn.command_groups)
    return parser


def _add_command_subparsers(
    parser: argparse.ArgumentParser,
    groups: list[CommandGroup],
) -> None:
    if not groups:
        return
    subparsers = parser.add_subparsers(dest="command")
    for cmd in groups:
        cmd_parser = subparsers.add_parser(cmd.name, help=cmd.help)
        _add_args(cmd_parser, cmd.args)
        cmd_parser.set_defaults(command=cmd.name)


# ---------------------------------------------------------------------------
# Shared argument definitions (reused across provider CLI variants)
# ---------------------------------------------------------------------------

_ARG_CONFIG = Arg(["--config"], {"help": "Path to a YAML config file"})
_ARG_ENV_FILE = Arg(
    ["--env-file"],
    {
        "action": "append",
        "default": [],
        "help": "Additional .env file loaded before expanding --config",
    },
)
_ARG_COUNTRY = Arg(["--country"], {"help": "Two-letter country code"})
_ARG_SEARCH_GC = Arg(["--search"], {"help": "Filter by name, institution ID, or BIC"})
_ARG_SEARCH_EB = Arg(["--search"], {"help": "Filter by name"})

# -- GoCardless-specific arguments -------------------------------------------

_ARG_GC_SECRET_ID = Arg(
    ["--secret-id"],
    {"default": os.getenv("GOCARDLESS_SECRET_ID"), "help": "GoCardless secret ID"},
)
_ARG_GC_SECRET_KEY = Arg(
    ["--secret-key"],
    {"default": os.getenv("GOCARDLESS_SECRET_KEY"), "help": "GoCardless secret key"},
)
_ARG_GC_REQUISITION_ID_REQUIRED = Arg(
    ["--requisition-id"], {"required": True, "help": "Requisition ID"}
)
_ARG_GC_REQUISITION_ID_OPTIONAL = Arg(
    ["--requisition-id"], {"help": "Requisition ID to delete"}
)
_ARG_GC_INSTITUTION_ID_REQUIRED = Arg(["--institution-id"], {"required": True})
_ARG_GC_INSTITUTION_ID_OPTIONAL = Arg(["--institution-id"], {"help": "Institution ID"})
_ARG_GC_REFERENCE_REQUIRED = Arg(["--reference"], {"required": True})
_ARG_GC_REFERENCE_OPTIONAL = Arg(
    ["--reference"], {"help": "Reference for the new link"}
)
_ARG_GC_REDIRECT_URL = Arg(
    ["--redirect-url"],
    {
        "default": os.getenv(
            "GOCARDLESS_REDIRECT_URL", DEFAULT_GOCARDLESS_REDIRECT_URL
        ),
        "help": "Redirect URL",
    },
)
_ARG_GC_USER_LANGUAGE = Arg(["--user-language"], {"help": "User language"})

# -- Enable Banking-specific arguments ---------------------------------------

_ARG_EB_APPLICATION_ID = Arg(
    ["--application-id"],
    {
        "default": os.getenv("ENABLE_BANKING_APPLICATION_ID"),
        "help": "Enable Banking application ID",
    },
)
_ARG_EB_PRIVATE_KEY_PATH = Arg(
    ["--private-key-path"],
    {
        "default": os.getenv("ENABLE_BANKING_PRIVATE_KEY_PATH"),
        "help": "Path to RSA private key (PEM)",
    },
)
_ARG_EB_REDIRECT_URL = Arg(
    ["--redirect-url"],
    {
        "default": os.getenv(
            "ENABLE_BANKING_REDIRECT_URL", DEFAULT_ENABLEBANKING_REDIRECT_URL
        ),
        "help": "OAuth redirect URL",
    },
)
_ARG_EB_SESSION_STORE_PATH = Arg(
    ["--session-store-path"],
    {
        "default": os.getenv("ENABLE_BANKING_SESSION_STORE_PATH"),
        "help": "Session storage directory",
    },
)
_ARG_EB_SESSION_ID_REQUIRED = Arg(
    ["--session-id"], {"required": True, "help": "Session ID"}
)
_ARG_EB_SESSION_ID_OPTIONAL = Arg(["--session-id"], {"help": "Session ID to delete"})
_ARG_EB_COUNTRY_REQUIRED = Arg(
    ["--country"], {"required": True, "help": "Two-letter country code"}
)
_ARG_EB_ASPSP_NAME_REQUIRED = Arg(["--aspsp-name"], {"required": True})
_ARG_EB_ASPSP_NAME_OPTIONAL = Arg(["--aspsp-name"], {"help": "ASPSP name"})
_ARG_EB_PSU_TYPE = Arg(
    ["--psu-type"],
    {"default": "personal", "choices": ["personal", "business"], "help": "PSU type"},
)
_ARG_EB_ACCESS_DAYS = Arg(
    ["--access-days"],
    {"type": int, "default": 90, "help": "Access validity in days"},
)
_ARG_EB_CALLBACK_HOST = Arg(["--callback-host"], {"help": "Callback server host"})
_ARG_EB_CALLBACK_PORT = Arg(
    ["--callback-port"], {"type": int, "help": "Callback server port"}
)
_ARG_EB_NO_BROWSER = Arg(
    ["--no-browser"], {"action": "store_true", "help": "Do not open browser"}
)

# ---------------------------------------------------------------------------
# Shared command group shapes
# ---------------------------------------------------------------------------

_GC_BANKS = CommandGroup(
    name="banks",
    help="List banks",
    args=[_ARG_COUNTRY, _ARG_SEARCH_GC],
)
_GC_LINKS = CommandGroup(name="links", help="List bank links")
_GC_ACCOUNTS = CommandGroup(name="accounts", help="List linked accounts")
_GC_CREATE_LINK_COMMON = CommandGroup(
    name="create-link",
    help="Create a bank link",
    args=[_ARG_GC_REDIRECT_URL, _ARG_GC_USER_LANGUAGE],
)
_GC_DELETE_LINK = CommandGroup(
    name="delete-link",
    help="Delete a bank link",
)

_EB_BANKS = CommandGroup(
    name="banks",
    help="List banks",
    args=[_ARG_COUNTRY, _ARG_SEARCH_EB],
)
_EB_LINKS = CommandGroup(name="links", help="List bank links")
_EB_ACCOUNTS = CommandGroup(name="accounts", help="List linked accounts")
_EB_DELETE_LINK = CommandGroup(
    name="delete-link",
    help="Delete a bank link",
)
_EB_CREATE_LINK_COMMON = CommandGroup(
    name="create-link",
    help="Create a bank link",
    args=[
        _ARG_EB_PSU_TYPE,
        _ARG_EB_ACCESS_DAYS,
        _ARG_EB_CALLBACK_HOST,
        _ARG_EB_CALLBACK_PORT,
        _ARG_EB_NO_BROWSER,
    ],
)

# ---------------------------------------------------------------------------
# Multi-provider CLI definitions (args with required=True)
# ---------------------------------------------------------------------------

GC_CLI_MULTI = ProviderCLIDef(
    name="gocardless",
    help="GoCardless tools",
    global_args=[_ARG_CONFIG, _ARG_ENV_FILE, _ARG_GC_SECRET_ID, _ARG_GC_SECRET_KEY],
    command_groups=[
        _GC_BANKS,
        _GC_LINKS,
        CommandGroup(
            name="delete-link",
            help="Delete a bank link",
            args=[_ARG_GC_REQUISITION_ID_REQUIRED],
        ),
        CommandGroup(
            name="create-link",
            help="Create a bank link",
            args=[
                _ARG_GC_INSTITUTION_ID_REQUIRED,
                _ARG_GC_REFERENCE_REQUIRED,
                _ARG_GC_REDIRECT_URL,
                _ARG_GC_USER_LANGUAGE,
            ],
        ),
        _GC_ACCOUNTS,
    ],
)

EB_CLI_MULTI = ProviderCLIDef(
    name="enablebanking",
    help="Enable Banking tools",
    global_args=[
        _ARG_CONFIG,
        _ARG_ENV_FILE,
        _ARG_EB_APPLICATION_ID,
        _ARG_EB_PRIVATE_KEY_PATH,
        _ARG_EB_REDIRECT_URL,
        _ARG_EB_SESSION_STORE_PATH,
    ],
    command_groups=[
        CommandGroup(
            name="banks",
            help="List banks",
            args=[_ARG_EB_COUNTRY_REQUIRED, _ARG_SEARCH_EB],
        ),
        _EB_LINKS,
        CommandGroup(
            name="delete-link",
            help="Delete a bank link",
            args=[_ARG_EB_SESSION_ID_REQUIRED],
        ),
        CommandGroup(
            name="create-link",
            help="Create a bank link",
            args=[
                _ARG_EB_COUNTRY_REQUIRED,
                _ARG_EB_ASPSP_NAME_REQUIRED,
                _ARG_EB_PSU_TYPE,
                _ARG_EB_ACCESS_DAYS,
                _ARG_EB_CALLBACK_HOST,
                _ARG_EB_CALLBACK_PORT,
                _ARG_EB_NO_BROWSER,
            ],
        ),
        _EB_ACCOUNTS,
    ],
)


# ---------------------------------------------------------------------------
# Dedicated CLI definitions (args without required=True — interactive fallback)
# ---------------------------------------------------------------------------

GC_CLI_DEDICATED = ProviderCLIDef(
    name="gocardless",
    help="Dedicated GoCardless CLI",
    global_args=[_ARG_CONFIG, _ARG_ENV_FILE, _ARG_GC_SECRET_ID, _ARG_GC_SECRET_KEY],
    command_groups=[
        _GC_BANKS,
        _GC_LINKS,
        CommandGroup(
            name="delete-link",
            help="Delete a bank link",
            args=[_ARG_GC_REQUISITION_ID_OPTIONAL],
        ),
        CommandGroup(
            name="create-link",
            help="Create a bank link",
            args=[
                _ARG_GC_INSTITUTION_ID_OPTIONAL,
                _ARG_GC_REFERENCE_OPTIONAL,
                _ARG_GC_REDIRECT_URL,
                _ARG_GC_USER_LANGUAGE,
            ],
        ),
        _GC_ACCOUNTS,
    ],
)

EB_CLI_DEDICATED = ProviderCLIDef(
    name="enablebanking",
    help="Dedicated Enable Banking CLI",
    global_args=[
        _ARG_CONFIG,
        _ARG_ENV_FILE,
        _ARG_EB_APPLICATION_ID,
        _ARG_EB_PRIVATE_KEY_PATH,
        _ARG_EB_REDIRECT_URL,
        _ARG_EB_SESSION_STORE_PATH,
    ],
    command_groups=[
        _EB_BANKS,
        _EB_LINKS,
        CommandGroup(
            name="delete-link",
            help="Delete a bank link",
            args=[_ARG_EB_SESSION_ID_OPTIONAL],
        ),
        CommandGroup(
            name="create-link",
            help="Create a bank link",
            args=[
                _ARG_COUNTRY,
                _ARG_EB_ASPSP_NAME_OPTIONAL,
                _ARG_EB_PSU_TYPE,
                _ARG_EB_ACCESS_DAYS,
                _ARG_EB_CALLBACK_HOST,
                _ARG_EB_CALLBACK_PORT,
                _ARG_EB_NO_BROWSER,
            ],
        ),
        _EB_ACCOUNTS,
    ],
)
