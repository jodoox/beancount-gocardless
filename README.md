# beancount-openbanking

`beancount-openbanking` fetches bank data from supported open banking providers
and emits Beancount directives through a shared normalized importer and CLI surface.

Today the project supports:

- GoCardless Bank Account Data
- Enable Banking

## Why this project

This project offers a practical Beancount import pipeline for open banking data.

- One importer API across multiple providers.
- Provider-specific CLIs for bank discovery, link creation, and session
  inspection.
- YAML configuration with `.env` expansion and config-relative paths.
- Backward compatibility for existing `beancount_gocardless` users while the
  multi-provider surface settles.

## Status

The project is still actively evolving - things may break.

## Naming and compatibility

The published distribution is still called `beancount-gocardless`, while the
active Python package and primary CLI have already moved to the broader
`beancount_openbanking` / `beancount-openbanking` names.

- PyPI distribution: `beancount-gocardless`
- Python package: `beancount_openbanking`
- Primary multi-provider CLI: `beancount-openbanking`
- Dedicated GoCardless helper CLI: `beancount-gocardless`
- Dedicated Enable Banking helper CLI: `beancount-enablebanking`

During the transition, imports and CLIs emit a warning about the planned rename.
Set `BEANCOUNT_OPENBANKING_SILENCE_RENAME_WARNING=1` to suppress it.

## Install

```bash
pip install beancount-gocardless
```

## Quick start

1. Create a YAML config for your provider.
2. Keep secrets in `.env`, `env_files` or inline in the YAML.
3. Use the CLI to create or inspect bank links.
4. List accounts and copy the provider account IDs into the config.
5. Run the importer against your Beancount ledger.

Example:

```bash
beancount-gocardless --config gocardless.yaml
beancount-openbanking gocardless --config gocardless.yaml accounts
python my_import.py extract ./gocardless.yaml --existing ./ledger.bean
```

## Configuration

Configuration files are YAML. String values may reference environment variables
with `$VAR` or `${VAR}`.

Expansion order:

1. nearest `.env` file found from the config directory upward
2. files listed in `env_files`
3. values in the top-level `env` mapping
4. current process environment

Path fields in YAML are resolved relative to the YAML file. For Enable Banking
that includes `private_key_path` and `session_store_path`.

The generic importer expects an explicit `provider` field. The provider-specific
CLIs (`beancount-gocardless` and `beancount-enablebanking`) infer it when
loading a config, which keeps older single-provider configs working.

### GoCardless config

```yaml
provider: gocardless
env_files:
  - .env

secret_id: $GOCARDLESS_SECRET_ID
secret_key: $GOCARDLESS_SECRET_KEY

accounts:
  - id: "<ACCOUNT_ID>"
    asset_account: "Assets:Banks:Revolut:Checking"
    booking_statuses: ["booked", "pending"]
```

### Enable Banking config

```yaml
provider: enablebanking
env_files:
  - .env

application_id: $ENABLE_BANKING_APPLICATION_ID
private_key_path: $ENABLE_BANKING_PRIVATE_KEY_PATH
redirect_url: "http://127.0.0.1:8765/callback"
session_store_path: ".secrets/enablebanking-sessions"

accounts:
  - id: "<ACCOUNT_UID>"
    asset_account: "Assets:Banks:BNP:Checking"
    booking_statuses: ["booked", "pending"]
```

`session_store_path` is a directory. Each Enable Banking authorization is stored
as a separate JSON file inside it so multiple sessions can coexist.

Per-account fields:

- `id`: provider account identifier
- `asset_account`: target Beancount account
- `metadata`: static metadata added to emitted directives
- `booking_statuses`: `booked` and/or `pending`
- `preferred_balance_type`: preferred balance when several are returned
- `exclude_default_metadata`: remove default metadata keys
- `metadata_fields`: map output metadata keys to provider field paths
- `days_back`: transaction lookback window

Default metadata keys:

- `ref`
- `creditorName`
- `debtorName`
- `bookingDate`

## Importer usage

```python
import beangulp
from beancount_openbanking import BankImporter

if __name__ == "__main__":
    ingest = beangulp.Ingest([BankImporter()])
    ingest()
```

Run it with a provider config:

```bash
python my_import.py extract ./gocardless.yaml --existing ./ledger.bean
python my_import.py extract ./enablebanking.yaml --existing ./ledger.bean
```

If you want `identify()` to match a non-default config filename during
interactive `beangulp` workflows, initialize the importer with that filename.

## CLI usage

List GoCardless banks:

```bash
beancount-openbanking gocardless --config gocardless.yaml banks --country FR --search bnp
```

Create a GoCardless bank link:

```bash
beancount-openbanking gocardless --config gocardless.yaml create-link \
  --institution-id REVOLUT_REVOGB21 \
  --reference revolut-main
```

GoCardless helper CLI:

```bash
beancount-gocardless --config gocardless.yaml
beancount-gocardless links
beancount-gocardless create-link --institution-id REVOLUT_REVOGB21 --reference revolut-main
beancount-gocardless delete-link --requisition-id <REQUISITION_ID>
```

List Enable Banking banks:

```bash
beancount-openbanking enablebanking --config enablebanking.yaml banks --country FR
```

Create an Enable Banking link:

```bash
beancount-openbanking enablebanking --config enablebanking.yaml create-link \
  --country FR \
  --aspsp-name "BNP Paribas"
```

List or delete Enable Banking sessions:

```bash
beancount-openbanking enablebanking --config enablebanking.yaml links
beancount-openbanking enablebanking --config enablebanking.yaml delete-link \
  --session-id <SESSION_ID>
```

Enable Banking helper CLI:

```bash
beancount-enablebanking --config enablebanking.yaml
beancount-enablebanking links
beancount-enablebanking accounts
```

## Development

The repository uses `uv` for dependency management and packaging. `mise` tasks
are provided as a small convenience layer for the common checks.

Install the project with development dependencies:

```bash
uv sync --extra test --extra lint --extra docs --extra typecheck
```

Run the main checks:

```bash
uv run pytest -q
uv run ruff check .
uv run ty check src/
uv run sphinx-build -b html docs docs/_build/html
```

Or use the bundled tasks:

```bash
mise run test
mise run lint
mise run typecheck
mise run docs
```

## Repository layout

- `src/beancount_openbanking/`: primary package, importer, CLI, providers
- `src/beancount_gocardless/`: compatibility shim for the legacy package name
- `tests/`: regression and provider behavior coverage
- `docs/`: Sphinx documentation

## More documentation

- `docs/workflow.rst`: end-to-end usage flow
- `docs/importer.rst`: config model and importer behavior
- `docs/client.rst`: provider API surface
- `docs/compatibility.rst`: naming and migration notes
