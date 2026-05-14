"""Session storage for Enable Banking API sessions.

Sessions are persisted as individual JSON files in a directory, keyed by
session_id. This allows multiple bank authorizations (e.g. personal and
business accounts at the same ASPSP) without overwriting existing sessions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ..providers.enablebanking_types import EnableBankingSession

logger = logging.getLogger(__name__)


class SessionStore:
    """Directory-based storage for Enable Banking session data.

    Each session is saved as a separate JSON file named ``{session_id}.json``
    inside the configured directory.

    Args:
        path: Directory path for session storage.
    """

    def __init__(self, path: str | None = None) -> None:
        if path is None:
            raise ValueError("SessionStore requires a directory path")
        self.path = Path(path)

    def _file_path(self, session_id: str) -> Path:
        return self.path / f"{session_id}.json"

    def save(self, session: EnableBankingSession) -> None:
        """Persist a session.

        Args:
            session: Session data. Must contain a ``session_id``.
        """
        session_id = session.session_id
        if not session_id:
            raise ValueError("session data must contain 'session_id'")

        self.path.mkdir(parents=True, exist_ok=True)
        file_path = self._file_path(session_id)
        logger.debug("Persisting session to: %s", file_path)
        file_path.write_text(
            session.model_dump_json(by_alias=True, indent=2),
            encoding="utf-8",
        )

    def load(self, session_id: str) -> EnableBankingSession | None:
        """Load a specific session by ID.

        Returns:
            Session data, or ``None`` if not found.
        """
        file_path = self._file_path(session_id)
        if file_path.exists():
            logger.debug("Loading session from: %s", file_path)
            raw = json.loads(file_path.read_text(encoding="utf-8"))
            return EnableBankingSession.model_validate(raw)
        return None

    def load_all(self) -> list[EnableBankingSession]:
        """Load all stored sessions.

        Returns:
            List of session data.
        """
        sessions: list[EnableBankingSession] = []
        if not self.path.exists():
            return sessions

        for file_path in sorted(self.path.glob("*.json")):
            try:
                raw = json.loads(file_path.read_text(encoding="utf-8"))
                sessions.append(EnableBankingSession.model_validate(raw))
            except (json.JSONDecodeError, OSError, ValueError):
                logger.warning("Skipping unreadable session file: %s", file_path)

        return sessions

    def list(self) -> list[str]:
        """List all stored session IDs."""
        ids: list[str] = []
        if not self.path.exists():
            return ids

        for file_path in self.path.glob("*.json"):
            try:
                raw = json.loads(file_path.read_text(encoding="utf-8"))
                sid = raw.get("session_id") or raw.get("sessionId")
                if sid:
                    ids.append(sid)
            except (json.JSONDecodeError, OSError):
                pass

        return sorted(ids)

    def delete(self, session_id: str) -> None:
        """Remove a session."""
        file_path = self._file_path(session_id)
        if file_path.exists():
            file_path.unlink()

    def exists(self, session_id: str | None = None) -> bool:
        """Check if a session exists.

        Args:
            session_id: If provided, check for that specific session.
                Otherwise check if *any* session exists.

        Returns:
            True if the session exists, False otherwise.
        """
        if not self.path.exists():
            return False

        if session_id is not None:
            return self._file_path(session_id).exists()

        return any(self.path.glob("*.json"))
