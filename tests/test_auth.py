"""Tests for the auth package (JWT signing, callback server, session store)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import jwt
import pytest
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from beancount_openbanking.auth.callback_server import (
    CallbackResult,
    wait_for_oauth_callback,
)
from beancount_openbanking.auth.jwt_signing import build_auth_headers, build_jwt
from beancount_openbanking.auth.enablebanking_types import (
    EnableBankingAccountDetail,
    EnableBankingSession,
)
from beancount_openbanking.auth.session_manager import SessionManager
from beancount_openbanking.auth.session_store import SessionStore

# ---------------------------------------------------------------------------
# Shared test fixture: RSA key pair
# ---------------------------------------------------------------------------

_PRIVATE_KEY_PEM: str | None = None
_PUBLIC_KEY: object = None


def _rsa_key_pair() -> tuple[str, object]:
    global _PRIVATE_KEY_PEM, _PUBLIC_KEY
    if _PRIVATE_KEY_PEM is not None:
        return _PRIVATE_KEY_PEM, _PUBLIC_KEY

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _PRIVATE_KEY_PEM = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    _PUBLIC_KEY = private_key.public_key()
    return _PRIVATE_KEY_PEM, _PUBLIC_KEY


# ---------------------------------------------------------------------------
# jwt_signing tests
# ---------------------------------------------------------------------------


class TestBuildJwt:
    def test_build_jwt_returns_signed_token(self, tmp_path: Path) -> None:
        pem, public_key = _rsa_key_pair()
        key_path = tmp_path / "test_key.pem"
        key_path.write_text(pem)

        token = build_jwt(
            application_id="test-app-id",
            private_key_path=str(key_path),
            ttl_seconds=3600,
        )

        payload = jwt.decode(
            token, public_key, algorithms=["RS256"], options={"verify_aud": False}
        )
        assert payload["iss"] == "enablebanking.com"
        assert payload["aud"] == "api.enablebanking.com"
        assert "iat" in payload
        assert "exp" in payload
        assert payload["exp"] - payload["iat"] == 3600

    def test_build_jwt_ttl_too_large(self, tmp_path: Path) -> None:
        pem, _ = _rsa_key_pair()
        key_path = tmp_path / "test_key.pem"
        key_path.write_text(pem)

        with pytest.raises(ValueError, match="maximum 86400 seconds"):
            build_jwt(
                application_id="test-app-id",
                private_key_path=str(key_path),
                ttl_seconds=86401,
            )

    def test_build_jwt_missing_key_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            build_jwt(
                application_id="test-app-id",
                private_key_path="/nonexistent/key.pem",
                ttl_seconds=3600,
            )

    def test_build_jwt_accepts_max_ttl(self, tmp_path: Path) -> None:
        pem, public_key = _rsa_key_pair()
        key_path = tmp_path / "test_key.pem"
        key_path.write_text(pem)

        token = build_jwt(
            application_id="test-app-id",
            private_key_path=str(key_path),
            ttl_seconds=86400,
        )

        payload = jwt.decode(
            token, public_key, algorithms=["RS256"], options={"verify_aud": False}
        )
        assert payload["exp"] - payload["iat"] == 86400

    def test_build_jwt_uses_correct_headers(self, tmp_path: Path) -> None:
        pem, public_key = _rsa_key_pair()
        key_path = tmp_path / "test_key.pem"
        key_path.write_text(pem)

        token = build_jwt(
            application_id="test-app-id",
            private_key_path=str(key_path),
            ttl_seconds=3600,
        )
        headers = jwt.get_unverified_header(token)
        assert headers["typ"] == "JWT"
        assert headers["alg"] == "RS256"
        assert headers["kid"] == "test-app-id"


class TestBuildAuthHeaders:
    def test_returns_expected_headers(self, tmp_path: Path) -> None:
        pem, _ = _rsa_key_pair()
        key_path = tmp_path / "test_key.pem"
        key_path.write_text(pem)

        headers = build_auth_headers(
            application_id="test-app-id",
            private_key_path=str(key_path),
        )

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert headers["Accept"] == "application/json"
        assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# callback_server tests
# ---------------------------------------------------------------------------


class TestWaitForOauthCallback:
    def test_receives_callback_with_code_and_state(self) -> None:
        import time
        import urllib.request

        result: list[CallbackResult] = []

        def make_request() -> None:
            time.sleep(0.2)
            try:
                urllib.request.urlopen(
                    "http://127.0.0.1:18765/?code=auth-code-123&state=test-state-456"
                )
            except Exception:
                pass

        thread = threading.Thread(target=make_request, daemon=True)
        thread.start()

        cb = wait_for_oauth_callback(host="127.0.0.1", port=18765, timeout=5)
        result.append(cb)

        assert len(result) == 1
        assert result[0].code == "auth-code-123"
        assert result[0].state == "test-state-456"
        assert result[0].error is None

    def test_callback_with_error(self) -> None:
        import time
        import urllib.request

        def make_request() -> None:
            time.sleep(0.2)
            try:
                urllib.request.urlopen(
                    "http://127.0.0.1:18766/"
                    "?error=access_denied&error_description=User+denied"
                )
            except Exception:
                pass

        thread = threading.Thread(target=make_request, daemon=True)
        thread.start()

        with pytest.raises(RuntimeError, match="access_denied"):
            wait_for_oauth_callback(host="127.0.0.1", port=18766, timeout=5)

    def test_timeout_raises(self) -> None:
        with pytest.raises(TimeoutError, match="Timeout"):
            wait_for_oauth_callback(host="127.0.0.1", port=18767, timeout=1)

    def test_callback_without_code_raises(self) -> None:
        import time
        import urllib.request

        def make_request() -> None:
            time.sleep(0.2)
            try:
                urllib.request.urlopen("http://127.0.0.1:18768/?state=no-code-here")
            except Exception:
                pass

        thread = threading.Thread(target=make_request, daemon=True)
        thread.start()

        with pytest.raises(RuntimeError, match="No authorization code"):
            wait_for_oauth_callback(host="127.0.0.1", port=18768, timeout=5)


# ---------------------------------------------------------------------------
# session_store tests
# ---------------------------------------------------------------------------


class TestSessionStore:
    def _make_session(
        self,
        session_id: str = "sess-1",
    ) -> EnableBankingSession:
        return EnableBankingSession(
            session_id=session_id,
            accounts=["acc-1"],
            status="AUTHORIZED",
        )

    def test_save_and_load(self, tmp_path: Path) -> None:
        store = SessionStore(str(tmp_path))
        session = self._make_session("sess-1")

        store.save(session)
        loaded = store.load("sess-1")

        assert loaded is not None
        assert loaded.session_id == "sess-1"
        assert loaded.accounts == ["acc-1"]
        assert loaded.status == "AUTHORIZED"

    def test_load_missing_returns_none(self, tmp_path: Path) -> None:
        store = SessionStore(str(tmp_path))
        assert store.load("nonexistent") is None

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c"
        store = SessionStore(str(nested))
        session = self._make_session("sess-1")

        store.save(session)
        assert nested.exists()
        assert (nested / "sess-1.json").exists()

    def test_save_raises_on_missing_session_id(self, tmp_path: Path) -> None:
        store = SessionStore(str(tmp_path))
        session = EnableBankingSession()

        with pytest.raises(ValueError, match="session_id"):
            store.save(session)

    def test_list_returns_sorted_ids(self, tmp_path: Path) -> None:
        store = SessionStore(str(tmp_path))
        store.save(self._make_session("sess-b"))
        store.save(self._make_session("sess-a"))
        store.save(self._make_session("sess-c"))

        ids = store.list()
        assert ids == ["sess-a", "sess-b", "sess-c"]

    def test_list_empty_directory(self, tmp_path: Path) -> None:
        store = SessionStore(str(tmp_path))
        assert store.list() == []

    def test_list_nonexistent_directory(self, tmp_path: Path) -> None:
        store = SessionStore(str(tmp_path / "nonexistent"))
        assert store.list() == []

    def test_exists_checks_specific_session(self, tmp_path: Path) -> None:
        store = SessionStore(str(tmp_path))
        store.save(self._make_session("sess-1"))

        assert store.exists("sess-1") is True
        assert store.exists("sess-2") is False

    def test_exists_checks_any_session(self, tmp_path: Path) -> None:
        store = SessionStore(str(tmp_path))
        assert store.exists() is False

        store.save(self._make_session("sess-1"))
        assert store.exists() is True

    def test_delete_removes_file(self, tmp_path: Path) -> None:
        store = SessionStore(str(tmp_path))
        store.save(self._make_session("sess-1"))
        assert (tmp_path / "sess-1.json").exists()

        store.delete("sess-1")
        assert not (tmp_path / "sess-1.json").exists()

    def test_delete_nonexistent_does_not_raise(self, tmp_path: Path) -> None:
        store = SessionStore(str(tmp_path))
        store.delete("nonexistent")

    def test_load_all(self, tmp_path: Path) -> None:
        store = SessionStore(str(tmp_path))
        store.save(self._make_session("sess-1"))
        store.save(self._make_session("sess-2"))

        all_sessions = store.load_all()
        assert len(all_sessions) == 2
        assert {s.session_id for s in all_sessions} == {"sess-1", "sess-2"}

    def test_load_all_empty(self, tmp_path: Path) -> None:
        store = SessionStore(str(tmp_path))
        assert store.load_all() == []

    def test_load_all_skips_corrupted_files(self, tmp_path: Path) -> None:
        store = SessionStore(str(tmp_path))
        store.save(self._make_session("sess-1"))
        (tmp_path / "corrupt.json").write_text("not valid json", encoding="utf-8")
        (tmp_path / "empty.json").write_text("", encoding="utf-8")

        all_sessions = store.load_all()
        assert len(all_sessions) == 1
        assert all_sessions[0].session_id == "sess-1"

    def test_session_file_contents(self, tmp_path: Path) -> None:
        """Verify that saved JSON has the expected shape."""
        store = SessionStore(str(tmp_path))
        session = self._make_session("sess-1")
        store.save(session)

        raw = json.loads((tmp_path / "sess-1.json").read_text(encoding="utf-8"))
        assert raw.get("session_id") == "sess-1" or raw.get("sessionId") == "sess-1"
        assert raw["accounts"] == ["acc-1"]
        assert raw["status"] == "AUTHORIZED"

    def test_round_trip_preserves_accounts_data(self, tmp_path: Path) -> None:
        store = SessionStore(str(tmp_path))
        session = EnableBankingSession(
            session_id="sess-1",
            accounts=["acc-1"],
            status="AUTHORIZED",
        )
        store.save(session)
        loaded = store.load("sess-1")

        assert loaded is not None
        assert loaded.session_id == "sess-1"
        assert loaded.accounts == ["acc-1"]
        assert loaded.status == "AUTHORIZED"


# ---------------------------------------------------------------------------
# session_manager tests
# ---------------------------------------------------------------------------


class TestSessionManager:
    def _manager(
        self, **overrides: object
    ) -> tuple[SessionManager, MagicMock, MagicMock]:
        http = MagicMock(name="http")
        store = MagicMock(name="store")
        kwargs: dict[str, object] = {
            "http": http,
            "build_headers": lambda: {"Authorization": "Bearer test"},
            "session_store": store,
            "redirect_url": "http://localhost/callback",
        }
        kwargs.update(overrides)
        return SessionManager(**kwargs), http, store

    @staticmethod
    def _patched_send(responses: list[MagicMock]) -> MagicMock:
        """Patch the network layer that ``EnableBankingApiClient`` calls.

        Returns a context manager whose ``.call_args_list`` exposes every URL
        the manager actually requested, with the corresponding response
        returned in order. This exercises URL building, header signing, and
        ``raise_for_status`` — none of which a private-method mock covers.
        """

        def fake_send(
            http: object, method: str, url: str, **kwargs: object
        ) -> MagicMock:
            return responses.pop(0)

        return patch(
            "beancount_openbanking.auth.api_client.send_with_rate_limit_retry",
            side_effect=fake_send,
        )

    def test_list_sessions_requires_session_store(self) -> None:
        manager, _, _ = self._manager(session_store=None)

        with pytest.raises(RuntimeError, match="session storage is not configured"):
            manager.list_sessions()

    def test_start_authorization_posts_to_auth_endpoint(self) -> None:
        manager, _, _ = self._manager()
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"url": "https://aspsp.example/auth"}
        with self._patched_send([response]) as mock_send:
            result = manager.start_authorization(
                aspsp_name="Revolut",
                aspsp_country="GB",
            )

        assert result["url"] == "https://aspsp.example/auth"
        assert isinstance(result["state"], str) and len(result["state"]) > 0
        call = mock_send.call_args_list[0]
        assert call.args[1] == "POST"
        assert call.args[2] == "https://api.enablebanking.com/auth"
        body = call.kwargs["json"]
        assert body["aspsp"] == {"name": "Revolut", "country": "GB"}
        assert body["state"] == result["state"]
        assert call.kwargs["headers"]["Authorization"] == "Bearer test"

    def test_get_session_hits_session_endpoint(self) -> None:
        manager, _, _ = self._manager()
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "session_id": "sess-1",
            "accounts": [{"uid": "acc-1", "name": "Checking"}],
        }
        with self._patched_send([response]) as mock_send:
            session = manager.get_session("sess-1")

        assert isinstance(session, EnableBankingSession)
        assert session.session_id == "sess-1"
        assert session.accounts[0] == "acc-1"
        assert mock_send.call_args.args[1:] == (
            "GET",
            "https://api.enablebanking.com/sessions/sess-1",
        )

    def test_delete_session_swallows_request_exception(self) -> None:
        manager, _, store = self._manager()
        with patch(
            "beancount_openbanking.auth.api_client.send_with_rate_limit_retry",
            side_effect=requests.RequestException("network down"),
        ):
            manager.delete_session("sess-1")
        store.delete.assert_called_once_with("sess-1")

    def test_delete_session_propagates_unexpected_exception(self) -> None:
        manager, _, _ = self._manager()
        with (
            patch(
                "beancount_openbanking.auth.api_client.send_with_rate_limit_retry",
                side_effect=ValueError("boom"),
            ),
            pytest.raises(ValueError, match="boom"),
        ):
            manager.delete_session("sess-1")

    def test_list_sessions_merges_and_saves_fresh_data(self) -> None:
        manager, _, store = self._manager()
        stored = EnableBankingSession(
            session_id="sess-1",
            accounts=["acc-1"],
            status="AUTHORIZED",
        )
        store.load_all.return_value = [stored]
        fresh_response = MagicMock()
        fresh_response.raise_for_status.return_value = None
        fresh_response.json.return_value = {
            "session_id": "sess-1",
            "status": "ACTIVE",
            "accounts": ["acc-1", "acc-2"],
        }
        with self._patched_send([fresh_response]):
            sessions = manager.list_sessions()

        assert len(sessions) == 1
        merged = sessions[0]
        # Fresh data wins on overlapping fields; stored fields are preserved.
        assert merged.status == "ACTIVE"
        assert merged.accounts == ["acc-1", "acc-2"]
        assert merged.session_id == "sess-1"
        store.save.assert_called_once()
        assert isinstance(store.save.call_args.args[0], EnableBankingSession)

    def test_list_sessions_falls_back_to_local_copy_on_refresh_failure(self) -> None:
        manager, _, store = self._manager()
        stored = EnableBankingSession(
            session_id="sess-1",
            accounts=["acc-1"],
            status="AUTHORIZED",
        )
        store.load_all.return_value = [stored]
        with patch(
            "beancount_openbanking.auth.api_client.send_with_rate_limit_retry",
            side_effect=requests.RequestException("boom"),
        ):
            sessions = manager.list_sessions()

        assert sessions == [stored]
        store.save.assert_not_called()

    def test_list_sessions_preserves_nested_accounts_data(self) -> None:
        # The merge via ``{**stored.model_dump(), **fresh.model_dump()}`` re-
        # instantiates nested Pydantic models as plain dicts. Verify that
        # the saved session still exposes ``accounts_data`` as proper
        # ``EnableBankingAccountDetail`` instances (not raw dicts).
        manager, _, store = self._manager()
        stored = EnableBankingSession(
            session_id="sess-1",
            accounts=["acc-1"],
            accounts_data=[
                EnableBankingAccountDetail(
                    uid="acc-1",
                    name="Checking",
                    currency="EUR",
                )
            ],
        )
        store.load_all.return_value = [stored]
        fresh_response = MagicMock()
        fresh_response.raise_for_status.return_value = None
        fresh_response.json.return_value = {
            "session_id": "sess-1",
            "status": "ACTIVE",
            "accounts": ["acc-1", "acc-2"],
            "accounts_data": [
                {"uid": "acc-1", "name": "Checking", "currency": "EUR"},
                {"uid": "acc-2", "name": "Savings", "currency": "EUR"},
            ],
        }
        with self._patched_send([fresh_response]):
            sessions = manager.list_sessions()

        merged = sessions[0]
        assert len(merged.accounts_data) == 2
        assert all(
            isinstance(detail, EnableBankingAccountDetail)
            for detail in merged.accounts_data
        )
        assert {d.uid for d in merged.accounts_data} == {"acc-1", "acc-2"}
        saved_session = store.save.call_args.args[0]
        assert isinstance(saved_session, EnableBankingSession)
        assert isinstance(saved_session.accounts_data[0], EnableBankingAccountDetail)

    def test_authorize_interactive_rejects_state_mismatch(self) -> None:
        manager, _, _ = self._manager()
        start_response = MagicMock()
        start_response.raise_for_status.return_value = None
        start_response.json.return_value = {
            "url": "https://aspsp.example/auth",
            "state": "expected-state",
        }
        with (
            self._patched_send([start_response]),
            patch(
                "beancount_openbanking.auth.session_manager.wait_for_oauth_callback",
                return_value=MagicMock(state="attacker-state", code="code", error=""),
            ),
            pytest.raises(RuntimeError, match="OAuth state mismatch"),
        ):
            manager.authorize_interactive(
                aspsp_name="Revolut",
                aspsp_country="GB",
                open_browser=False,
            )

    def test_authorize_interactive_invokes_url_callback(self) -> None:
        manager, _, _ = self._manager()
        with patch(
            "beancount_openbanking.auth.session_manager.secrets.token_urlsafe",
            return_value="state-1",
        ):
            start_response = MagicMock()
            start_response.raise_for_status.return_value = None
            start_response.json.return_value = {
                "url": "https://aspsp.example/auth",
                "state": "state-1",
            }
            create_response = MagicMock()
            create_response.raise_for_status.return_value = None
            create_response.json.return_value = {"session_id": "sess-1"}
            refresh_response = MagicMock()
            refresh_response.raise_for_status.return_value = None
            refresh_response.json.return_value = {
                "session_id": "sess-1",
                "accounts": [{"uid": "acc-1"}],
            }
            with (
                self._patched_send(
                    [start_response, create_response, refresh_response]
                ) as mock_send,
                patch(
                    "beancount_openbanking.auth.session_manager.wait_for_oauth_callback",
                    return_value=MagicMock(state="state-1", code="code", error=""),
                ) as mock_wait,
            ):
                seen_urls: list[str] = []
                session = manager.authorize_interactive(
                    aspsp_name="Revolut",
                    aspsp_country="GB",
                    open_browser=False,
                    on_authorization_url=seen_urls.append,
                )

        assert seen_urls == ["https://aspsp.example/auth"]
        mock_wait.assert_called_once()
        assert isinstance(session, EnableBankingSession)
        assert session.session_id == "sess-1"
        # All three calls hit the Enable Banking base URL with bearer auth.
        for call in mock_send.call_args_list:
            assert call.args[2].startswith("https://api.enablebanking.com/")
            assert call.kwargs["headers"]["Authorization"] == "Bearer test"

    def test_create_session_from_code_refreshes_session_details(self) -> None:
        manager, _, store = self._manager()
        post_response = MagicMock()
        post_response.raise_for_status.return_value = None
        post_response.json.return_value = {"session_id": "session-1"}
        get_response = MagicMock()
        get_response.raise_for_status.return_value = None
        get_response.json.return_value = {
            "session_id": "session-1",
            "accounts": [{"uid": "acc-1", "name": "Checking"}],
        }

        with self._patched_send([post_response, get_response]) as mock_send:
            session = manager.create_session_from_code("auth-code")

        assert isinstance(session, EnableBankingSession)
        assert session.accounts[0] == "acc-1"
        assert mock_send.call_count == 2
        assert mock_send.call_args_list[0].args[1:] == (
            "POST",
            "https://api.enablebanking.com/sessions",
        )
        assert mock_send.call_args_list[1].args[1:] == (
            "GET",
            "https://api.enablebanking.com/sessions/session-1",
        )
        store.save.assert_called_once()
        saved = store.save.call_args.args[0]
        assert isinstance(saved, EnableBankingSession)
