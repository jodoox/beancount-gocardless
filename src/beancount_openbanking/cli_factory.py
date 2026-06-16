"""Provider factory: build a provider from CLI args or a config file.

Both ``gocardless_cli.build_gocardless_provider`` and
``enablebanking_cli.build_enablebanking_provider`` previously inlined the
same "config or args" decision. This module centralizes that logic so each
provider only needs to declare how to construct itself from a parsed
config (``from_config``) or from raw args (``from_args``) and how to
detect whether the args carry usable credentials (``credentials_from_args``).
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Protocol, TypeVar

from .config import EnableBankingConfig, GoCardlessConfig, load_config

if TYPE_CHECKING:
    from .providers.base import Provider


class _FactoryProvider(Protocol):
    """Surface required for :func:`build_provider`.

    Concrete providers must declare ``from_config`` and ``from_args``
    classmethods, plus a ``credentials_from_args`` staticmethod.
    """

    @classmethod
    def from_config(cls, config: object) -> "Provider": ...
    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "Provider": ...
    @staticmethod
    def credentials_from_args(args: argparse.Namespace) -> tuple[str, str] | None: ...


T = TypeVar("T", bound="Provider")


def build_provider(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    *,
    provider_name: str,
    config_class: type[GoCardlessConfig] | type[EnableBankingConfig],
    provider_class: type[_FactoryProvider],
    config_label: str,
) -> T:
    """Build ``provider_class`` from either ``--config`` or the CLI flags.

    ``provider_name`` is the value used to discriminate the config union
    when loading a YAML file. ``config_class`` is the expected concrete
    config type (used for the post-load isinstance check). ``config_label``
    is the human-friendly name shown in the error message (e.g.
    ``"GoCardless"`` or ``"Enable Banking"``).
    """
    if getattr(args, "config", None):
        config = load_config(
            args.config,
            env_files=args.env_file,
            default_provider=provider_name,
        )
        if not isinstance(config, config_class):
            parser.error(f"{args.config} is not a {config_label} config file")
        return provider_class.from_config(config)  # type: ignore[return-value]

    if provider_class.credentials_from_args(args) is None:
        parser.error(
            f"{config_label} credentials are required. Use --config or pass "
            f"the provider-specific flags."
        )
    return provider_class.from_args(args)  # type: ignore[return-value]
