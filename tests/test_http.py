"""Tests for shared HTTP utilities in providers/base.py."""

from __future__ import annotations
from unittest.mock import MagicMock, patch
import requests
from beancount_openbanking.providers.base import (
    create_cached_session,
    send_with_rate_limit_retry,
    strip_headers_hook,
)


class TestStripHeadersHook:
    def test_strips_cache_control_headers(self) -> None:
        response = MagicMock()
        response.headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Date": "Wed, 01 Jan 2024 00:00:00 GMT",
        }

        result = strip_headers_hook(response)

        assert result is response
        assert "Content-Type" in response.headers
        assert "Date" in response.headers
        assert "Cache-Control" not in response.headers

    def test_preserves_whitelisted_headers_only(self) -> None:
        response = MagicMock()
        response.headers = {
            "Content-Type": "application/json",
            "Content-Encoding": "gzip",
            "Content-Language": "en",
            "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
            "Location": "https://example.com",
            "Date": "Wed, 01 Jan 2024 00:00:00 GMT",
            "X-Custom-Header": "should-go",
            "ETag": "should-go-too",
        }

        strip_headers_hook(response)

        preserved = {
            "Content-Type",
            "Content-Encoding",
            "Content-Language",
            "Last-Modified",
            "Location",
            "Date",
        }
        for h in preserved:
            assert h in response.headers
        assert "X-Custom-Header" not in response.headers
        assert "ETag" not in response.headers


class TestCreateCachedSession:
    @patch("beancount_openbanking.providers.base.requests_cache.CachedSession")
    def test_uses_defaults_and_attaches_hook(self, mock_cached_session) -> None:
        mock_hooks = {"response": []}
        mock_cached_session.return_value.hooks = mock_hooks

        session = create_cached_session({})

        mock_cached_session.assert_called_once_with(
            backend="sqlite",
            expire_after=0,
            old_data_on_error=True,
            match_headers=False,
            cache_control=False,
            cache_name="openbanking",
        )
        assert session is mock_cached_session.return_value
        assert strip_headers_hook in mock_hooks["response"]

    @patch("beancount_openbanking.providers.base.requests_cache.CachedSession")
    def test_allows_custom_cache_name(self, mock_cached_session) -> None:
        create_cached_session({}, default_cache_name="gocardless")
        assert mock_cached_session.call_args.kwargs["cache_name"] == "gocardless"

    @patch("beancount_openbanking.providers.base.requests_cache.CachedSession")
    def test_user_options_override_defaults(self, mock_cached_session) -> None:
        create_cached_session({"expire_after": 3600, "backend": "memory"})
        kwargs = mock_cached_session.call_args.kwargs
        assert kwargs["expire_after"] == 3600
        assert kwargs["backend"] == "memory"

    def test_none_returns_plain_session(self) -> None:
        session = create_cached_session(None)
        assert isinstance(session, requests.Session)
        assert not hasattr(session, "cache")


class TestSendWithRateLimitRetry:
    def test_returns_ok_response_immediately(self) -> None:
        session = MagicMock()
        ok_response = MagicMock()
        ok_response.status_code = 200
        session.request.return_value = ok_response

        response = send_with_rate_limit_retry(session, "GET", "https://example.com")

        assert response is ok_response
        session.request.assert_called_once_with("GET", "https://example.com")

    def test_retries_on_429_and_succeeds(self) -> None:
        session = MagicMock()
        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.headers = {}
        ok_response = MagicMock()
        ok_response.status_code = 200
        session.request.side_effect = [rate_limited, ok_response]

        with patch("beancount_openbanking.providers.base.time.sleep") as mock_sleep:
            response = send_with_rate_limit_retry(
                session, "GET", "https://example.com", backoff_base=1
            )

        assert response is ok_response
        assert session.request.call_count == 2
        mock_sleep.assert_called_once_with(1.0)

    def test_uses_retry_after_header(self) -> None:
        session = MagicMock()
        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "5"}
        ok_response = MagicMock()
        ok_response.status_code = 200
        session.request.side_effect = [rate_limited, ok_response]

        with patch("beancount_openbanking.providers.base.time.sleep") as mock_sleep:
            response = send_with_rate_limit_retry(session, "GET", "https://example.com")

        assert response is ok_response
        mock_sleep.assert_called_once_with(5.0)

    def test_gives_up_after_max_retries(self) -> None:
        session = MagicMock()
        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.headers = {}
        session.request.return_value = rate_limited

        with patch("beancount_openbanking.providers.base.time.sleep"):
            response = send_with_rate_limit_retry(
                session, "GET", "https://example.com", max_retries=2, backoff_base=1
            )

        assert response is rate_limited
        assert session.request.call_count == 3  # initial + 2 retries
