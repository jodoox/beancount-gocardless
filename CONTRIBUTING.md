# Contributing

The project is small on purpose: a shared importer layer, provider adapters,
and a compatibility shim for the legacy GoCardless package name.

## Local setup

The repo uses `uv` for dependency management.

```bash
uv sync --extra test --extra lint --extra docs --extra typecheck
```

If you use `mise`, a few helper tasks are already defined:

```bash
mise run test
mise run lint
mise run typecheck
mise run docs
```

## What to run before opening a PR

```bash
uv run pytest -q
uv run ruff check .
uv run ty check src/
uv run sphinx-build -b html docs docs/_build/html
```

The GitHub Actions workflow runs the same categories of checks across the
supported Python versions.

## Project shape

- `src/beancount_openbanking/`: primary package, normalized importer, provider implementations, CLI
- `src/beancount_gocardless/`: backward-compatibility shim and aliases
- `tests/`: importer, CLI, provider, and compatibility coverage
- `docs/`: Sphinx documentation

## Notes for changes

- Prefer extending the normalized provider model over adding provider-specific behavior directly to the importer.
- Keep compatibility behavior explicit and tested when changing the legacy shim.
- Treat docs as part of the product surface, not as an afterthought. If a change affects config, CLI behavior, or naming, update the README or Sphinx docs in the same patch.
