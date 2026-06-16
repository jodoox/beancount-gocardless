# Changelog

All notable changes to `beancount-gocardless` / `beancount-openbanking` are
documented in this file. The distribution name remains `beancount-gocardless`
on PyPI; the Python package and primary CLI are `beancount_openbanking` /
`beancount-openbanking`.

## [0.2.0] - 2026-06-16

### Added

- **Enable Banking provider** as a first-class peer of GoCardless. Includes
  full data-flow coverage: list ASPSPs (banks), OAuth authorization with
  local callback server, session persistence, account discovery, balance and
  transaction fetching, and a normalized Beancount importer.
- **`SessionManager`** that owns the Enable Banking OAuth flow and session
  lifecycle. Composed into `EnableBankingProvider` for account discovery.
- **`beancount-openbanking` multi-provider CLI** with `gocardless` and
  `enablebanking` subcommands, plus dedicated `beancount-gocardless` and
  `beancount-enablebanking` CLIs with an interactive questionary front-end.
- **Provider protocol and shared CLI dispatch** so new providers can plug in
  with minimal ceremony.
- **YAML configuration with `ImportConfig` discriminated union**, `.env`
  expansion, and config-relative paths.
- **Type checking with `ty`** wired into CI.

### Changed

- Package reorganized from a single `beancount_gocardless` module into a
  `beancount_openbanking` package with `auth/`, `cli/`, `config/`, and
  `providers/` submodules. The legacy `beancount_gocardless` package is kept
  as a thin shim re-exporting the new public API.
- HTTP utilities extracted from `providers/base.py` into `providers/http.py`
  and shared across providers.
- CLI surface tightened: shared dispatch maps, consistent table rendering,
  and a single interactive mixin for the dedicated CLIs.
- Tightened the `build_provider()` return type from `object` to `Provider`
  in config.

### Deprecated

- The `beancount_gocardless` package is now a legacy shim. Imports from it
  continue to work but emit no warnings yet; a future release will issue a
  `DeprecationWarning` and, eventually, the package will be removed in favor
  of a `beancount_openbanking` distribution.

## [0.1.14] - 2025-XX-XX

Previous release. Interactive CLI with expiry awareness.
