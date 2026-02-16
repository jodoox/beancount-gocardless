import os
from pathlib import Path
from typing import Optional

__all__ = ["load_dotenv"]


def load_dotenv(dotenv_path: Optional[str] = None) -> None:
    """Load environment variables from a ``.env`` file.

    Parses simple ``KEY=VALUE`` lines, ignoring comments and blank lines.
    Values already present in the environment are not overwritten.

    If no path is given, searches for a ``.env`` file in the current
    directory and each parent directory, stopping at the first one found.

    Args:
        dotenv_path: Explicit path to a ``.env`` file. If ``None``, searches
            the current directory and its parents.
    """
    if dotenv_path:
        search_paths = [Path(dotenv_path)]
    else:
        # Search in current and parent directories
        current = Path.cwd().resolve()
        search_paths = [current / ".env"] + [p / ".env" for p in current.parents]

    for path in search_paths:
        if path.exists() and path.is_file():
            try:
                with open(path, "r") as f:
                    for line in f:
                        line = line.strip()
                        # Ignore comments and empty lines
                        if not line or line.startswith("#"):
                            continue
                        # Basic KEY=VALUE parsing
                        if "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            # Strip quotes and whitespace
                            value = value.strip().strip("'\"")
                            # Only set if not already present in environment
                            if key and key not in os.environ:
                                os.environ[key] = value
                return  # Stop after the first .env file found and successfully read
            except Exception:
                # Silently fail if we can't read a specific .env file
                continue
