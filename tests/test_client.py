"""Tests for the GoCardless API client.

Covers token refresh, 401 retry, pagination, rate-limiting (429 back-off),
edge cases, and endpoint constant usage.
"""

import time
from unittest.mock import patch, MagicMock

import pytest
import requests

from beancount_gocardless.client import (
    GoCardlessClient,
    strip_headers_hook,
    ENDPOINT_TOKEN_NEW,
    MAX_PAGINATION_PAGES,
    RATE_LIMIT_MAX_RETRIES,
)


def _make_response(status_code=200, json_data=None, headers=None):
    """Build a fake requests.Response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.headers = headers or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


@pytest.fixture
def client():
    """Return a GoCardlessClient with mocked session (no real HTTP)."""
    with patch("beancount_gocardless.client.requests_cache.CachedSession") as mock_cs:
        mock_session = MagicMock()
        mock_session.hooks = {"response": []}
        mock_cs.return_value = mock_session
        c = GoCardlessClient("test-id", "test-key")
        # Pre-set token so tests don't trigger get_token automatically
        c._token = "initial-token"
        c._token_expires_at = time.monotonic() + 300
    return c


class TestStripHeadersHook:
    """Tests for the response-header stripping hook."""

    def test_preserves_allowed_headers(self):
        """Only headers in the allow-list survive."""
        resp = MagicMock()
        resp.headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Custom": "value",
            "Date": "Mon, 01 Jan 2026 00:00:00 GMT",
        }
        real_headers = dict(resp.headers)
        resp.headers = real_headers

        result = strip_headers_hook(resp)

        assert "Content-Type" in result.headers
        assert "Date" in result.headers
        assert "Cache-Control" not in result.headers
        assert "X-Custom" not in result.headers

    def test_empty_headers(self):
        """No error when response has no extra headers."""
        resp = MagicMock()
        resp.headers = {}
        result = strip_headers_hook(resp)
        assert result is resp


class TestTokenManagement:
    """Tests for token acquisition and the token property."""

    @patch("beancount_gocardless.client.requests.post")
    def test_get_token_sets_access(self, mock_post, client):
        """get_token stores the access token from the API response."""
        mock_post.return_value = _make_response(
            json_data={"access": "new-access-token", "refresh": "r"}
        )
        client.get_token()
        assert client._token == "new-access-token"
        mock_post.assert_called_once()

    @patch("beancount_gocardless.client.requests.post")
    def test_get_token_raises_on_http_error(self, mock_post, client):
        """get_token propagates HTTP errors."""
        mock_post.return_value = _make_response(status_code=403)
        with pytest.raises(requests.HTTPError):
            client.get_token()

    @patch("beancount_gocardless.client.requests.post")
    def test_token_property_fetches_when_none(self, mock_post):
        """Accessing .token triggers get_token when _token is None."""
        with patch(
            "beancount_gocardless.client.requests_cache.CachedSession"
        ) as mock_cs:
            mock_session = MagicMock()
            mock_session.hooks = {"response": []}
            mock_cs.return_value = mock_session
            c = GoCardlessClient("id", "key")

        mock_post.return_value = _make_response(
            json_data={"access": "auto-token", "refresh": "r"}
        )
        token = c.token
        assert token == "auto-token"

    def test_token_property_returns_cached(self, client):
        """Accessing .token returns existing token without API call."""
        assert client.token == "initial-token"


class TestRetryOn401:
    """Tests for automatic token refresh on 401 responses."""

    @patch("beancount_gocardless.client.requests.post")
    def test_retries_once_on_401(self, mock_post, client):
        """A 401 triggers token refresh and a second request."""
        first_resp = _make_response(status_code=401)
        first_resp.raise_for_status = MagicMock()
        second_resp = _make_response(json_data={"ok": True})

        client.session.request.side_effect = [first_resp, second_resp]
        mock_post.return_value = _make_response(
            json_data={"access": "refreshed-token", "refresh": "r"}
        )

        result = client.get("/test/")

        assert result == {"ok": True}
        assert client._token == "refreshed-token"
        assert client.session.request.call_count == 2

    def test_non_401_error_propagates(self, client):
        """Non-401 HTTP errors are raised, not silently swallowed."""
        error_resp = _make_response(status_code=500)
        client.session.request.return_value = error_resp

        with pytest.raises(requests.HTTPError):
            client.get("/fail/")

    def test_successful_request_no_retry(self, client):
        """A 200 response does not trigger any retry."""
        ok_resp = _make_response(json_data={"data": 1})
        client.session.request.return_value = ok_resp

        result = client.get("/ok/")

        assert result == {"data": 1}
        assert client.session.request.call_count == 1


class TestRateLimiting:
    """Tests for 429 back-off and retry logic."""

    @patch("beancount_gocardless.client.time.sleep")
    def test_retries_on_429_then_succeeds(self, mock_sleep, client):
        """Client retries after 429 and succeeds on next attempt."""
        rate_resp = _make_response(status_code=429)
        rate_resp.raise_for_status = MagicMock()
        ok_resp = _make_response(json_data={"ok": True})

        client.session.request.side_effect = [rate_resp, ok_resp]

        result = client.get("/rate-limited/")

        assert result == {"ok": True}
        mock_sleep.assert_called_once()

    @patch("beancount_gocardless.client.time.sleep")
    def test_respects_retry_after_header(self, mock_sleep, client):
        """Client uses Retry-After header value when present."""
        rate_resp = _make_response(status_code=429, headers={"Retry-After": "5"})
        rate_resp.raise_for_status = MagicMock()
        ok_resp = _make_response(json_data={"ok": True})

        client.session.request.side_effect = [rate_resp, ok_resp]

        client.get("/rate-limited/")

        mock_sleep.assert_called_once_with(5.0)

    @patch("beancount_gocardless.client.time.sleep")
    def test_gives_up_after_max_retries(self, mock_sleep, client):
        """Client raises after exhausting rate-limit retries."""
        rate_resp = _make_response(status_code=429)
        client.session.request.side_effect = [rate_resp] * (RATE_LIMIT_MAX_RETRIES + 1)

        with pytest.raises(requests.HTTPError):
            client.get("/always-429/")

        assert mock_sleep.call_count == RATE_LIMIT_MAX_RETRIES

    @patch("beancount_gocardless.client.time.sleep")
    def test_exponential_backoff_values(self, mock_sleep, client):
        """Back-off doubles on each retry when no Retry-After header."""
        rate_resp = _make_response(status_code=429)
        rate_resp.raise_for_status = MagicMock()
        ok_resp = _make_response(json_data={"ok": True})

        client.session.request.side_effect = [rate_resp, rate_resp, ok_resp]

        client.get("/backoff/")

        calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert calls == [1, 2]


class TestPagination:
    """Tests for transaction pagination and the max-page guard."""

    def test_follows_next_links(self, client):
        """Pagination follows next links and merges transactions."""
        page1 = {
            "transactions": {
                "booked": [{"id": "t1"}],
                "pending": [],
            },
            "next": "https://bankaccountdata.gocardless.com/api/v2/accounts/a1/transactions/?page=2",
        }
        page2 = {
            "transactions": {
                "booked": [{"id": "t2"}],
                "pending": [{"id": "p1"}],
            },
            "next": None,
        }

        ok1 = _make_response(json_data=page1)
        ok2 = _make_response(json_data=page2)
        client.session.request.side_effect = [ok1, ok2]

        result = client.get_account_transactions("a1", days_back=30)

        assert len(result.transactions["booked"]) == 2
        assert len(result.transactions["pending"]) == 1

    def test_no_pagination_when_next_is_none(self, client):
        """Single-page response works without pagination."""
        page = {
            "transactions": {
                "booked": [{"id": "t1"}],
                "pending": [],
            },
        }
        client.session.request.return_value = _make_response(json_data=page)

        result = client.get_account_transactions("a1", days_back=30)

        assert len(result.transactions["booked"]) == 1
        assert client.session.request.call_count == 1

    def test_max_page_guard(self, client):
        """Pagination stops after MAX_PAGINATION_PAGES to prevent infinite loops."""

        def make_page_response(*args, **kwargs):
            return _make_response(
                json_data={
                    "transactions": {"booked": [{"id": "tx"}], "pending": []},
                    "next": "https://bankaccountdata.gocardless.com/api/v2/accounts/a1/transactions/?page=999",
                }
            )

        client.session.request.side_effect = make_page_response

        result = client.get_account_transactions("a1", days_back=30)

        assert client.session.request.call_count == 1 + MAX_PAGINATION_PAGES
        assert len(result.transactions["booked"]) == 1 + MAX_PAGINATION_PAGES

    def test_empty_transactions_response(self, client):
        """Empty transaction response is handled without error."""
        page = {"transactions": {"booked": [], "pending": []}}
        client.session.request.return_value = _make_response(json_data=page)

        result = client.get_account_transactions("a1", days_back=30)

        assert len(result.transactions["booked"]) == 0
        assert len(result.transactions["pending"]) == 0

    def test_missing_transactions_key(self, client):
        """Response without transactions key defaults to empty lists."""
        page = {}
        client.session.request.return_value = _make_response(json_data=page)

        result = client.get_account_transactions("a1", days_back=30)

        assert len(result.transactions["booked"]) == 0
        assert len(result.transactions["pending"]) == 0

    def test_relative_next_url(self, client):
        """Pagination handles relative next URLs (not starting with BASE_URL)."""
        page1 = {
            "transactions": {
                "booked": [{"id": "t1"}],
                "pending": [],
            },
            "next": "/accounts/a1/transactions/?page=2",
        }
        page2 = {
            "transactions": {
                "booked": [{"id": "t2"}],
                "pending": [],
            },
            "next": None,
        }

        ok1 = _make_response(json_data=page1)
        ok2 = _make_response(json_data=page2)
        client.session.request.side_effect = [ok1, ok2]

        result = client.get_account_transactions("a1", days_back=30)

        assert len(result.transactions["booked"]) == 2


class TestEdgeCases:
    """Tests for error handling and edge cases."""

    def test_get_returns_json(self, client):
        """get() returns parsed JSON from the response."""
        client.session.request.return_value = _make_response(json_data={"key": "value"})
        assert client.get("/endpoint/") == {"key": "value"}

    def test_post_returns_json(self, client):
        """post() returns parsed JSON from the response."""
        client.session.request.return_value = _make_response(
            json_data={"created": True}
        )
        assert client.post("/endpoint/", data={"a": 1}) == {"created": True}

    def test_delete_returns_json(self, client):
        """delete() returns parsed JSON from the response."""
        client.session.request.return_value = _make_response(
            json_data={"deleted": True}
        )
        assert client.delete("/endpoint/") == {"deleted": True}

    def test_check_cache_status_no_token(self):
        """check_cache_status works when no token is set."""
        with patch(
            "beancount_gocardless.client.requests_cache.CachedSession"
        ) as mock_cs:
            mock_session = MagicMock()
            mock_session.hooks = {"response": []}
            mock_cs.return_value = mock_session
            c = GoCardlessClient("id", "key")

        mock_cache = MagicMock()
        mock_cache.contains.return_value = False
        c.session.cache = mock_cache

        result = c.check_cache_status("GET", "http://example.com")
        assert result["key_exists"] is False

    def test_check_cache_status_expired(self, client):
        """check_cache_status reports expired entries."""
        mock_cache = MagicMock()
        mock_cache.contains.return_value = True
        mock_cached_resp = MagicMock()
        mock_cached_resp.is_expired = True
        mock_cache.get_response.return_value = mock_cached_resp
        client.session.cache = mock_cache

        result = client.check_cache_status("GET", "http://example.com")
        assert result["key_exists"] is True
        assert result["is_expired"] is True

    def test_check_cache_status_handles_exception(self, client):
        """check_cache_status handles cache read errors gracefully."""
        mock_cache = MagicMock()
        mock_cache.contains.return_value = True
        mock_cache.get_response.side_effect = KeyError("corrupt")
        client.session.cache = mock_cache

        result = client.check_cache_status("GET", "http://example.com")
        assert result["is_expired"] is None

    def test_get_all_accounts_skips_failed(self, client):
        """get_all_accounts skips accounts that raise RequestException."""
        mock_req = MagicMock()
        mock_req.accounts = ["acc1", "acc2"]
        mock_req.access_valid_for_days = 90
        mock_req.created = "2026-01-01T00:00:00Z"
        mock_req.status = "LN"
        mock_req.id = "req1"
        mock_req.reference = "ref1"
        mock_req.institution_id = "BANK1"

        mock_account = MagicMock()
        mock_account.model_dump.return_value = {"id": "acc2", "status": "READY"}

        with patch.object(client, "get_requisitions", return_value=[mock_req]):
            with patch.object(
                client,
                "get_account",
                side_effect=[requests.RequestException("fail"), mock_account],
            ):
                accounts = client.get_all_accounts()

        assert len(accounts) == 1
        assert accounts[0]["id"] == "acc2"


class TestEndpointConstants:
    """Verify that endpoint constants are used (not hardcoded strings)."""

    def test_token_endpoint_constant_exists(self):
        """ENDPOINT_TOKEN_NEW is defined and matches expected path."""
        assert ENDPOINT_TOKEN_NEW == "/token/new/"

    def test_max_pagination_pages_constant(self):
        """MAX_PAGINATION_PAGES is a positive integer."""
        assert isinstance(MAX_PAGINATION_PAGES, int)
        assert MAX_PAGINATION_PAGES > 0
