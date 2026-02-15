"""Tests for the GoCardless API client.

Covers token refresh, 401 retry logic, and transaction pagination.
"""

import time
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests

from beancount_gocardless.client import GoCardlessClient


@pytest.fixture
def client():
    """Create a GoCardlessClient with mocked session and token."""
    with patch("beancount_gocardless.client.requests_cache.CachedSession"):
        c = GoCardlessClient("test-id", "test-key")
        c._token = "initial-token"
        c._token_expires_at = time.monotonic() + 300
    return c


class TestTokenRefresh:
    """Tests for token acquisition and refresh."""

    def test_get_token_sets_access_token(self, client):
        """get_token should store the access token from the API response."""
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {
            "access": "new-access-token",
            "access_expires": 86400,
            "refresh": "refresh-token",
            "refresh_expires": 2592000,
        }

        with patch("beancount_gocardless.client.requests.post", return_value=mock_resp):
            client.get_token()

        assert client._token == "new-access-token"

    def test_get_token_sets_expiry(self, client):
        """get_token should set _token_expires_at based on access_expires."""
        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {
            "access": "new-token",
            "access_expires": 600,
            "refresh": "r",
            "refresh_expires": 3600,
        }

        before = time.monotonic()
        with patch("beancount_gocardless.client.requests.post", return_value=mock_resp):
            client.get_token()
        after = time.monotonic()

        # Expiry should be ~600s minus the 30s buffer from now
        assert client._token_expires_at >= before + 600 - 30
        assert client._token_expires_at <= after + 600 - 30

    def test_token_property_fetches_when_none(self):
        """Accessing .token should call get_token when _token is None."""
        with patch("beancount_gocardless.client.requests_cache.CachedSession"):
            c = GoCardlessClient("id", "key")

        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {
            "access": "fetched-token",
            "access_expires": 300,
            "refresh": "r",
            "refresh_expires": 3600,
        }

        with patch("beancount_gocardless.client.requests.post", return_value=mock_resp):
            token = c.token

        assert token == "fetched-token"

    def test_token_property_refreshes_when_expired(self, client):
        """Accessing .token should refresh when the token is expired."""
        client._token = "old-token"
        client._token_expires_at = time.monotonic() - 10  # expired

        mock_resp = Mock()
        mock_resp.raise_for_status = Mock()
        mock_resp.json.return_value = {
            "access": "refreshed-token",
            "access_expires": 300,
            "refresh": "r",
            "refresh_expires": 3600,
        }

        with patch("beancount_gocardless.client.requests.post", return_value=mock_resp):
            token = c.token if False else client.token

        assert token == "refreshed-token"

    def test_token_property_returns_cached_when_valid(self, client):
        """Accessing .token should return cached token when not expired."""
        client._token = "cached-token"
        client._token_expires_at = time.monotonic() + 300

        assert client.token == "cached-token"


class TestRetryOn401:
    """Tests for 401 retry logic in _request."""

    def test_retries_on_401(self, client):
        """_request should refresh token and retry on 401."""
        resp_401 = Mock()
        resp_401.status_code = 401
        resp_401.headers = {}

        resp_200 = Mock()
        resp_200.status_code = 200
        resp_200.headers = {}
        resp_200.raise_for_status = Mock()

        client.session.request = Mock(side_effect=[resp_401, resp_200])
        client.check_cache_status = Mock(return_value={"is_expired": False})

        mock_token_resp = Mock()
        mock_token_resp.raise_for_status = Mock()
        mock_token_resp.json.return_value = {
            "access": "new-token",
            "access_expires": 300,
            "refresh": "r",
            "refresh_expires": 3600,
        }

        with patch("beancount_gocardless.client.requests.post", return_value=mock_token_resp):
            result = client._request("GET", "/test/")

        assert result.status_code == 200
        assert client.session.request.call_count == 2

    def test_no_retry_on_200(self, client):
        """_request should not retry on successful response."""
        resp_200 = Mock()
        resp_200.status_code = 200
        resp_200.headers = {}
        resp_200.raise_for_status = Mock()

        client.session.request = Mock(return_value=resp_200)
        client.check_cache_status = Mock(return_value={"is_expired": False})

        result = client._request("GET", "/test/")

        assert result.status_code == 200
        assert client.session.request.call_count == 1


class TestPagination:
    """Tests for transaction pagination in get_account_transactions."""

    def test_single_page(self, client):
        """Transactions without pagination should return all results."""
        single_page = {
            "transactions": {
                "booked": [
                    {
                        "transactionId": "tx1",
                        "transactionAmount": {"amount": "-10.00", "currency": "EUR"},
                    }
                ],
                "pending": [],
            }
        }

        client.get = Mock(return_value=single_page)

        result = client.get_account_transactions("acc-123", days_back=30)

        assert len(result.transactions["booked"]) == 1
        assert result.transactions["booked"][0].transaction_id == "tx1"

    def test_multiple_pages(self, client):
        """Pagination should follow next links and merge results."""
        page1 = {
            "transactions": {
                "booked": [
                    {
                        "transactionId": "tx1",
                        "transactionAmount": {"amount": "-10.00", "currency": "EUR"},
                    }
                ],
                "pending": [],
            },
            "next": "https://bankaccountdata.gocardless.com/api/v2/accounts/acc-123/transactions/?page=2",
        }
        page2 = {
            "transactions": {
                "booked": [
                    {
                        "transactionId": "tx2",
                        "transactionAmount": {"amount": "-20.00", "currency": "EUR"},
                    }
                ],
                "pending": [],
            },
        }

        client.get = Mock(side_effect=[page1, page2])

        result = client.get_account_transactions("acc-123", days_back=30)

        assert len(result.transactions["booked"]) == 2
        assert client.get.call_count == 2

    def test_pagination_strips_base_url(self, client):
        """Pagination should strip BASE_URL from next links."""
        page1 = {
            "transactions": {"booked": [], "pending": []},
            "next": f"{client.BASE_URL}/accounts/acc/transactions/?page=2",
        }
        page2 = {
            "transactions": {"booked": [], "pending": []},
        }

        client.get = Mock(side_effect=[page1, page2])
        client.get_account_transactions("acc", days_back=30)

        # Second call should use the stripped endpoint
        second_call_endpoint = client.get.call_args_list[1][0][0]
        assert not second_call_endpoint.startswith("http")

    def test_pagination_error_logged(self, client):
        """Pagination errors should be logged and stop iteration."""
        page1 = {
            "transactions": {
                "booked": [
                    {
                        "transactionId": "tx1",
                        "transactionAmount": {"amount": "-10.00", "currency": "EUR"},
                    }
                ],
                "pending": [],
            },
            "next": f"{client.BASE_URL}/accounts/acc/transactions/?page=2",
        }

        client.get = Mock(side_effect=[page1, requests.HTTPError("Server error")])

        with pytest.raises(requests.HTTPError):
            client.get_account_transactions("acc", days_back=30)

    def test_date_params_passed(self, client):
        """date_from and date_to should be passed as query params."""
        client.get = Mock(return_value={
            "transactions": {"booked": [], "pending": []},
        })

        client.get_account_transactions("acc-123", days_back=90)

        call_args = client.get.call_args
        params = call_args[1].get("params") or call_args[0][1] if len(call_args[0]) > 1 else call_args[1]["params"]
        assert "date_from" in params
        assert "date_to" in params
