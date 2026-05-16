"""Tests for the GoCardless provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from beancount_openbanking.providers import GoCardlessProvider, Institution


class TestGoCardlessProvider:
    @patch("beancount_openbanking.providers.gocardless.create_cached_session")
    def test_passes_cache_options_to_cached_session(self, mock_create_session) -> None:
        GoCardlessProvider(
            secret_id="test-id",
            secret_key="test-key",
            cache_options={"cache_name": "test-cache"},
        )

        mock_create_session.assert_called_once_with(
            {"cache_name": "test-cache"},
            default_cache_name="gocardless",
        )

    @patch("beancount_openbanking.providers.gocardless.create_cached_session")
    def test_empty_cache_options_enables_caching(self, mock_create_session) -> None:
        """Regression test: empty dict should enable caching, not disable it."""
        provider = GoCardlessProvider(
            secret_id="test-id",
            secret_key="test-key",
            cache_options={},
        )

        mock_create_session.assert_called_once_with(
            {},
            default_cache_name="gocardless",
        )
        assert provider.http is mock_create_session.return_value

    def test_none_cache_options_disables_caching(self) -> None:
        """cache_options=None should use regular session without caching."""
        import requests

        provider = GoCardlessProvider(
            secret_id="test-id",
            secret_key="test-key",
            cache_options=None,
        )

        assert isinstance(provider.http, requests.Session)
        assert (
            not isinstance(provider.http, type(provider.http))
            or "CachedSession" not in type(provider.http).__name__
        )

    def test_list_institutions(self) -> None:
        provider = GoCardlessProvider(secret_id="test-id", secret_key="test-key")
        with patch.object(
            provider,
            "_get",
            return_value=[
                {
                    "id": "REVOLUT_REVOGB21",
                    "name": "Revolut",
                    "bic": "REVOGB21",
                    "transaction_total_days": "90",
                    "countries": ["GB"],
                }
            ],
        ):
            institutions = provider.list_institutions(country="GB")

        assert institutions == [
            Institution(
                id="REVOLUT_REVOGB21",
                name="Revolut",
                bic="REVOGB21",
                transaction_total_days="90",
                countries=["GB"],
            )
        ]

    def test_list_requisitions(self) -> None:
        provider = GoCardlessProvider(secret_id="test-id", secret_key="test-key")
        with patch.object(
            provider,
            "_get",
            return_value={
                "results": [
                    {
                        "id": "req-1",
                        "created": "2024-01-01T12:00:00Z",
                        "redirect": "http://localhost",
                        "status": "LN",
                        "institution_id": "REVOLUT_REVOGB21",
                        "reference": "revolut",
                        "accounts": ["acc-1"],
                        "link": "https://example.com/auth",
                    }
                ]
            },
        ):
            requisitions = provider.list_requisitions()

        assert requisitions[0].reference == "revolut"
        assert requisitions[0].institution_id == "REVOLUT_REVOGB21"

    def test_create_requisition(self) -> None:
        provider = GoCardlessProvider(secret_id="test-id", secret_key="test-key")
        response = MagicMock()
        response.json.return_value = {
            "id": "req-1",
            "created": "2024-01-01T12:00:00Z",
            "redirect": "http://localhost",
            "status": "CR",
            "institution_id": "REVOLUT_REVOGB21",
            "reference": "revolut",
            "accounts": [],
            "link": "https://example.com/auth",
        }

        with patch.object(provider, "_request", return_value=response) as mock_request:
            requisition = provider.create_requisition(
                redirect_url="http://localhost",
                institution_id="REVOLUT_REVOGB21",
                reference="revolut",
            )

        assert requisition.link == "https://example.com/auth"
        mock_request.assert_called_once_with(
            "POST",
            "/requisitions/",
            data={
                "redirect": "http://localhost",
                "institution_id": "REVOLUT_REVOGB21",
                "reference": "revolut",
            },
        )
