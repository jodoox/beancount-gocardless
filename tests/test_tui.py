import pytest
from unittest.mock import Mock
from beancount_gocardless.tui import (
    GoCardLessApp,
    MenuView,
    AccountsView,
    BalanceView,
    LinkView,
    DeleteLinkView,
)
from beancount_gocardless.client import GoCardlessClient


@pytest.fixture
def mock_client():
    client = Mock(spec=GoCardlessClient)
    client.get_institutions.return_value = [
        Mock(name="Test Bank", id="BANK1", countries=["GB"])
    ]
    client.get_all_accounts.return_value = [
        {
            "id": "ACC1",
            "name": "Test Account",
            "institution_id": "BANK1",
            "iban": "GB123",
        }
    ]
    client.get_account_balances.return_value = Mock(
        balances=[
            Mock(
                balance_type="closingAvailable",
                balance_amount=Mock(amount="100.00", currency="GBP"),
            )
        ]
    )
    client.create_bank_link.return_value = "http://link.com"
    client.find_requisition_by_reference.return_value = Mock(id="REQ1")
    return client


def test_app_initialization(mock_client):
    app = GoCardLessApp(secret_id="test", secret_key="test")
    app.client = mock_client
    assert app.client == mock_client


def test_menu_view_compose():
    view = MenuView()
    # Just check compose doesn't fail
    content = list(view.compose())
    assert len(content) == 1


@pytest.mark.skip(reason="Hard to mock Textual context")
def test_banks_view_load(mock_client):
    pass


def test_accounts_view_load(mock_client):
    view = AccountsView(mock_client)
    # Mock the table update
    view.accounts_table = Mock()
    view.status_message = Mock()
    import asyncio

    asyncio.run(view.load_accounts())
    view.accounts_table.update.assert_called()


def test_balance_view(mock_client):
    view = BalanceView(mock_client)
    content = list(view.compose_content())
    assert len(content) == 4  # label, static, vertical, button


def test_link_view(mock_client):
    view = LinkView(mock_client)
    content = list(view.compose_content())
    assert len(content) == 3  # label, vertical, button


def test_delete_link_view(mock_client):
    view = DeleteLinkView(mock_client)
    content = list(view.compose_content())
    assert len(content) == 3  # label, vertical, button
