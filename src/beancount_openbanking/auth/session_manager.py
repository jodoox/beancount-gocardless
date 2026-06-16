"""OAuth authorization flow and session lifecycle for Enable Banking."""

from __future__ import annotations

import logging
import secrets
import webbrowser
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import requests

from .api_client import EnableBankingApiClient
from .callback_server import wait_for_oauth_callback
from .enablebanking_types import EnableBankingSession
from .session_store import SessionStore

logger = logging.getLogger(__name__)

ENDPOINT_AUTH = "/auth"
ENDPOINT_SESSIONS = "/sessions"
ENDPOINT_SESSION = "/sessions/{session_id}"

DEFAULT_ACCESS_DAYS = 90


class SessionManager:
    """Manages Enable Banking OAuth authorization and session lifecycle.

    Handles the full OAuth flow (start → user authorization → callback →
    session creation) as well as session CRUD and persistence. Composed into
    :class:`beancount_openbanking.providers.enablebanking.EnableBankingProvider`
    for account discovery.
    """

    def __init__(
        self,
        http: requests.Session,
        build_headers: Callable[[], dict[str, str]],
        session_store: SessionStore | None,
        redirect_url: str,
        timeout: int = 30,
    ) -> None:
        self.http = http
        self.session_store = session_store
        self.redirect_url = redirect_url
        self.api = EnableBankingApiClient(
            http=http,
            build_headers=build_headers,
            timeout=timeout,
        )

    def _require_session_store(self) -> SessionStore:
        if self.session_store is None:
            raise RuntimeError(
                "Enable Banking session storage is not configured. "
                "Set session_store_path to a writable directory."
            )
        return self.session_store

    def start_authorization(
        self,
        aspsp_name: str,
        aspsp_country: str,
        psu_type: str = "personal",
        access_days: int = DEFAULT_ACCESS_DAYS,
    ) -> dict[str, Any]:
        """Initiate an OAuth authorization with the ASPSP."""
        state = secrets.token_urlsafe(24)
        valid_until = (
            datetime.now(timezone.utc) + timedelta(days=access_days)
        ).isoformat()
        response = self.api.request(
            "POST",
            ENDPOINT_AUTH,
            json={
                "access": {"valid_until": valid_until},
                "aspsp": {"name": aspsp_name, "country": aspsp_country},
                "state": state,
                "redirect_url": self.redirect_url,
                "psu_type": psu_type,
            },
        )
        data = response.json()
        data["state"] = state
        return data

    def authorize_interactive(
        self,
        aspsp_name: str,
        aspsp_country: str,
        callback_host: str = "127.0.0.1",
        callback_port: int = 8765,
        psu_type: str = "personal",
        access_days: int = DEFAULT_ACCESS_DAYS,
        open_browser: bool = True,
        on_authorization_url: Callable[[str], None] | None = None,
    ) -> EnableBankingSession:
        """Run the full OAuth authorization flow interactively.

        The ``on_authorization_url`` callback receives the URL the user should
        visit. If unset, the URL is opened in the system browser when
        ``open_browser`` is true; if false, the URL is dropped (callers that
        need to surface it should pass a callback). The library does not
        print — that decision belongs to the caller.
        """
        authorization = self.start_authorization(
            aspsp_name=aspsp_name,
            aspsp_country=aspsp_country,
            psu_type=psu_type,
            access_days=access_days,
        )
        expected_state = authorization["state"]
        authorization_url = authorization["url"]

        if on_authorization_url is not None:
            on_authorization_url(authorization_url)
        elif open_browser:
            webbrowser.open(authorization_url)

        result = wait_for_oauth_callback(host=callback_host, port=callback_port)
        if result.state != expected_state:
            raise RuntimeError("OAuth state mismatch - possible CSRF attack")
        if result.error:
            raise RuntimeError(
                f"OAuth authorization failed: {result.error} - {result.error_description}"
            )
        if not result.code:
            raise RuntimeError("No authorization code received")
        return self.create_session_from_code(result.code)

    def create_session_from_code(self, code: str) -> EnableBankingSession:
        """Exchange an authorization code for a session.

        Enable Banking's ``POST /sessions`` response carries the
        ``session_id`` but only minimal account metadata. The follow-up
        ``GET /sessions/{id}`` returns the full session payload (account
        list, ASPSP, status), which is what callers actually want. Without
        the second call ``list_sessions()`` would later have to refresh
        anyway, so we pay one extra roundtrip now to avoid surprising the
        caller with a half-populated session.
        """
        raw = self.api.request("POST", ENDPOINT_SESSIONS, json={"code": code}).json()
        session_id = raw.get("session_id")
        if session_id:
            fresh = self.api.request(
                "GET",
                ENDPOINT_SESSION.format(session_id=session_id),
            ).json()
            raw = {**raw, **fresh}
        session = EnableBankingSession.from_api_response(raw)
        self._require_session_store().save(session)
        return session

    def get_session(self, session_id: str) -> EnableBankingSession:
        """Fetch a single session from the API."""
        raw = self.api.request(
            "GET", ENDPOINT_SESSION.format(session_id=session_id)
        ).json()
        return EnableBankingSession.from_api_response(raw)

    def delete_session(self, session_id: str) -> None:
        """Delete a session locally and revoke it at the ASPSP.

        If the remote revocation fails (network error, 4xx/5xx), the local
        copy is still removed but a warning is logged — the ASPSP-side session
        will eventually expire on its own. Use :meth:`get_session` to confirm
        the remote state if exactness matters.
        """
        try:
            self.api.request("DELETE", ENDPOINT_SESSION.format(session_id=session_id))
        except requests.RequestException as exc:
            logger.warning(
                "Failed to revoke session %s at the ASPSP: %s. "
                "Local copy will still be removed.",
                session_id,
                exc,
            )
        self._require_session_store().delete(session_id)

    def list_sessions(self) -> list[EnableBankingSession]:
        """Return all stored sessions with fresh API data.

        If a per-session refresh fails, the local copy is returned in place of
        the fresh data and a warning is logged. Callers that need to
        distinguish "stale" from "refreshed" should call :meth:`get_session`
        directly.
        """
        session_store = self._require_session_store()
        stored = session_store.load_all()
        sessions: list[EnableBankingSession] = []
        for session in stored:
            sid = session.session_id
            if not sid:
                continue
            try:
                fresh = self.get_session(sid)
                merged = EnableBankingSession.model_validate(
                    {**session.model_dump(), **fresh.model_dump()}
                )
                session_store.save(merged)
                sessions.append(merged)
            except requests.RequestException as exc:
                logger.warning(
                    "Failed to refresh session %s, returning local copy: %s",
                    sid,
                    exc,
                )
                sessions.append(session)
        return sessions
