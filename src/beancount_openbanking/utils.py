"""Small local helpers for dotenv file discovery."""

from __future__ import annotations

from pathlib import Path

__all__ = ["find_dotenv", "read_dotenv"]


def read_dotenv(dotenv_path: str | Path) -> dict[str, str]:
    """Read simple ``KEY=VALUE`` pairs from a dotenv file."""

    values: dict[str, str] = {}
    path = Path(dotenv_path)
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            values[key] = value
    return values


def find_dotenv(start: str | Path | None = None) -> Path | None:
    """Find the nearest ``.env`` file from ``start`` up through parents."""

    current = Path(start or Path.cwd()).resolve()
    search_paths = [current / ".env", *[parent / ".env" for parent in current.parents]]
    for path in search_paths:
        if path.exists() and path.is_file():
            return path
    return None
