# Domain Glossary

## Core concepts

- **Provider** — A bank data API (GoCardless or Enable Banking). Each has its own auth, session model, and API response shapes. Exposes a normalized `Provider` protocol.
- **Bank Importer** — A `beangulp.Importer` that reads a YAML config, fetches data from a Provider, and emits Beancount directives (`Transaction`, `Balance`).
- **Config** — YAML file describing which provider, credentials, and which accounts to import. Supports env-var expansion and config-relative paths.
- **Account** (provider-level) — A bank account as seen by the Provider. Has an ID, optional name/IBAN/currency, plus raw `provider_data`.
- **Transaction** (normalized) — A bank transaction normalized across providers. Contains amount, currency, dates, direction (credit/debit), booking status, remittance info, and raw `provider_data`.
- **Balance** (normalized) — A bank balance snapshot normalized across providers.
- **Requisition** (GoCardless) — A user-granted authorization linking one or more accounts to the application.
- **Session** (Enable Banking) — An OAuth-based authorization session linking accounts to the application, persisted as JSON files in a session store.
- **Bank Link** — A Requisition (GoCardless) or Session (Enable Banking). The CLI refers to both as "links" in user-facing output.
- **Booking Status** — Whether a transaction is `booked` (settled) or `pending`.
- **Transaction Direction** — Whether a transaction is a `credit` or `debit`.
- **Cache** — HTTP caching via `requests-cache`, configurable per provider, defaulting to SQLite backend.
- **Legacy Shim** — The `beancount_gocardless` package providing backward compatibility for the original single-provider API.

## CLI surface

- **Multi-provider CLI** (`beancount-openbanking`) — Primary CLI with `gocardless` and `enablebanking` subcommands.
- **Dedicated CLIs** (`beancount-gocardless`, `beancount-enablebanking`) — Provider-specific CLIs with identical command set plus interactive mode.
- **CLI Operations** — Command handlers (`GoCardlessOperations`, `EnableBankingOperations`) that translate provider data into user-facing tables (list banks, links, accounts; create/delete links).
- **Interactive Mode** — Questionary-based prompts available in the dedicated CLIs when run without a subcommand.

## Authentication

- **GoCardless Auth** — Secret ID + Secret Key → bearer token with ~1h expiry, auto-refreshed.
- **Enable Banking Auth** — Application ID + RSA private key → signed JWT → API auth. OAuth2 user authorization flow with local callback server.
- **Session Store** — File-based JSON persistence for Enable Banking sessions, keyed by `session_id`.

## Data flow (import)

Config → `load_config()` → `ImportConfig` (typed) → `build_provider()` → `Provider`
→ `Provider.list_accounts()` / `get_transactions()` / `get_balances()`
→ `BankImporter.extract()` filters, sorts, decorates → Beancount directives
