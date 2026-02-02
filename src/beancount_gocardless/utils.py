import os
from pathlib import Path
from typing import Optional


def load_dotenv(dotenv_path: Optional[str] = None) -> None:
    """
    Simple .env loader that searches in current and parent directories.
    Only handles simple KEY=VALUE pairs and ignores comments.
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
