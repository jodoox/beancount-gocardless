"""Importer configuration models and YAML loading."""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal, Union

import yaml
from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator
from typing_extensions import TypeAlias

from .providers.base import BookingStatus
from .utils import find_dotenv, read_dotenv


class ProviderName(str, Enum):
    """Supported bank data providers."""

    GOCARDLESS = "gocardless"
    ENABLEBANKING = "enablebanking"


class ImportTarget(BaseModel):
    """Configuration for importing a single bank account into Beancount."""

    id: str
    asset_account: str
    metadata: dict[str, object] = Field(default_factory=dict)
    booking_statuses: list[BookingStatus] = Field(
        default_factory=lambda: [BookingStatus.BOOKED, BookingStatus.PENDING]
    )
    preferred_balance_type: str | None = None
    exclude_default_metadata: list[str] = Field(default_factory=list)
    metadata_fields: dict[str, str] | None = None
    days_back: int = 180

    @field_validator("booking_statuses")
    @classmethod
    def validate_booking_statuses(
        cls, value: list[BookingStatus]
    ) -> list[BookingStatus]:
        if not value:
            raise ValueError("at least one booking status must be configured")
        return value


class ImportConfigBase(BaseModel):
    """Shared fields for importer configuration."""

    provider: ProviderName
    currency: str = "EUR"
    accounts: list[ImportTarget]

    @model_validator(mode="after")
    def validate_accounts(self) -> "ImportConfigBase":
        if not self.accounts:
            raise ValueError("at least one account must be configured")
        return self


class GoCardlessConfig(ImportConfigBase):
    """Configuration for the GoCardless provider."""

    provider: Literal[ProviderName.GOCARDLESS] = ProviderName.GOCARDLESS
    secret_id: str
    secret_key: str
    cache_options: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_credentials(self) -> "GoCardlessConfig":
        if not self.secret_id.strip():
            raise ValueError("secret_id is required for GoCardless")
        if not self.secret_key.strip():
            raise ValueError("secret_key is required for GoCardless")
        return self

    def build_provider(self) -> object:
        from .providers.gocardless import GoCardlessProvider

        return GoCardlessProvider(
            secret_id=self.secret_id,
            secret_key=self.secret_key,
            cache_options=self.cache_options or None,
        )


class EnableBankingConfig(ImportConfigBase):
    """Configuration for the Enable Banking provider."""

    provider: Literal[ProviderName.ENABLEBANKING] = ProviderName.ENABLEBANKING
    application_id: str
    private_key_path: str
    redirect_url: str = "http://127.0.0.1:8765/callback"
    session_store_path: str | None = None
    cache_options: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_credentials(self) -> "EnableBankingConfig":
        if not self.application_id.strip():
            raise ValueError("application_id is required for Enable Banking")
        if not self.private_key_path.strip():
            raise ValueError("private_key_path is required for Enable Banking")
        return self

    def build_provider(self) -> object:
        from .providers.enablebanking import EnableBankingProvider

        return EnableBankingProvider(
            application_id=self.application_id,
            private_key_path=self.private_key_path,
            redirect_url=self.redirect_url,
            session_store_path=self.session_store_path,
            cache_options=self.cache_options or None,
        )


ImportConfig: TypeAlias = Annotated[
    Union[GoCardlessConfig, EnableBankingConfig],
    Field(discriminator="provider"),
]

CONFIG_ADAPTER = TypeAdapter(ImportConfig)


ENV_VAR_PATTERN = re.compile(r"\$(\w+)|\$\{([^}]+)\}")


def _expand_env_vars(value: str, env: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1) or match.group(2)
        return env.get(key, match.group(0))

    return ENV_VAR_PATTERN.sub(replace, value)


def _expand_config_values(value: object, env: dict[str, str]) -> object:
    if isinstance(value, str):
        return _expand_env_vars(value, env)
    if isinstance(value, list):
        return [_expand_config_values(item, env) for item in value]
    if isinstance(value, dict):
        return {key: _expand_config_values(item, env) for key, item in value.items()}
    return value


def expand_config_values(
    raw: dict[str, object],
    env: dict[str, str],
    default_provider: str | None = None,
) -> dict[str, object]:
    """Expand env vars in config values, then strip ephemeral keys.

    This is the pure (I/O-free) transformation phase of config loading.
    """
    expanded = _expand_config_values(raw, env)
    expanded.pop("env", None)
    expanded.pop("env_files", None)
    if "provider" not in expanded and default_provider is not None:
        expanded["provider"] = default_provider
    return expanded


def read_raw_config(filepath: str) -> tuple[Path, dict[str, object]]:
    """Read a YAML config file from disk and return the raw dict.

    This is the only I/O phase of config loading.
    """
    config_path = Path(filepath)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config file must contain a YAML mapping")
    return config_path, raw


def _resolve_env_path(config_path: Path, candidate: str) -> Path:
    path = Path(candidate).expanduser()
    if path.is_absolute():
        return path
    return (config_path.parent / path).resolve()


def _resolve_relative_path(config_path: Path, value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return stripped
    return str(_resolve_env_path(config_path, stripped))


def resolve_paths(
    config: ImportConfig,
    config_path: Path,
) -> ImportConfig:
    if isinstance(config, EnableBankingConfig):
        return config.model_copy(
            update={
                "private_key_path": _resolve_relative_path(
                    config_path,
                    config.private_key_path,
                ),
                "session_store_path": _resolve_relative_path(
                    config_path,
                    config.session_store_path,
                ),
            }
        )
    return config


def _build_env(
    config_path: Path,
    config_dict: dict[str, object],
    env_files: list[str] | None = None,
) -> dict[str, str]:
    env: dict[str, str] = {}

    default_dotenv = find_dotenv(config_path.parent)
    if default_dotenv is not None:
        env.update(read_dotenv(default_dotenv))

    configured_files = config_dict.get("env_files") or []
    for candidate in [*configured_files, *(env_files or [])]:
        env.update(read_dotenv(_resolve_env_path(config_path, candidate)))

    inline_env = config_dict.get("env") or {}
    if inline_env:
        expanded_inline_env = {
            str(key): _expand_env_vars(str(value), {**env, **os_environ()})
            for key, value in inline_env.items()
        }
        env.update(expanded_inline_env)

    env.update(os_environ())
    return env


def os_environ() -> dict[str, str]:
    """Allow tests to patch environment resolution in one place."""

    import os

    return dict(os.environ)


def load_config(
    filepath: str,
    env_files: list[str] | None = None,
    default_provider: str | None = None,
) -> ImportConfig:
    """Load importer configuration from YAML.

    Composes the loading pipeline from public phases:
    ``read_raw_config`` → ``_build_env`` → ``expand_config_values``
    → Pydantic validation → ``resolve_paths``.
    """
    config_path, raw = read_raw_config(filepath)
    env = _build_env(config_path, raw, env_files=env_files)
    expanded = expand_config_values(raw, env, default_provider=default_provider)
    config = CONFIG_ADAPTER.validate_python(expanded)
    return resolve_paths(config, config_path)
