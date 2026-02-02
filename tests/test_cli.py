"""
Tests for the CLI module.

These tests use mocks to simulate user interactions with questionary
and the GoCardless client. No real API calls are made.
"""

import pytest
from unittest.mock import Mock, patch
from beancount_gocardless.cli import CLI


@pytest.fixture
def mock_cli():
    """Create a CLI instance with mock client."""
    cli = CLI(
        secret_id="mock-id",
        secret_key="mock-key",
        mock=True,
    )
    return cli


def test_cli_init_mock():
    """Test CLI initialization with mock client."""
    cli = CLI(
        secret_id="mock-id",
        secret_key="mock-key",
        mock=True,
    )
    assert cli.mock is True
    assert cli.client is not None


def test_cli_init_missing_creds():
    """Test CLI fails without credentials in non-mock mode."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(SystemExit) as exc:
            CLI(mock=False)
        assert exc.value.code == 1


def test_list_accounts_no_accounts(mock_cli):
    """Test list_accounts when no accounts exist."""
    mock_cli.client.list_accounts = Mock(return_value=[])

    with patch("beancount_gocardless.cli.questionary.select") as mock_select:
        mock_select.return_value.ask.return_value = None
        mock_cli.list_accounts_interactive()


def test_list_accounts_with_accounts(mock_cli):
    """Test list_accounts with accounts."""
    accounts = [
        {
            "id": "ACC1",
            "name": "Test Account",
            "iban": "GB123",
            "institution_id": "BANK1",
            "requisition_reference": "ref1",
        }
    ]
    mock_cli.client.list_accounts = Mock(return_value=accounts)

    with (
        patch("beancount_gocardless.cli.questionary.select") as mock_select,
    ):
        mock_select.return_value.ask.return_value = "BANK1 - Test Account (GB123)"
        mock_cli.list_accounts_interactive()


@patch("beancount_gocardless.cli.questionary.select")
def test_show_account_menu_view_balance(mock_select, mock_cli):
    """Test _show_account_menu with view balance action."""
    account = {
        "id": "ACC1",
        "name": "Test Account",
        "iban": "GB123",
        "institution_id": "BANK1",
        "requisition_reference": "ref1",
    }

    mock_balance = Mock()
    mock_balance.balances = [
        Mock(
            balance_type="closingAvailable",
            balance_amount=Mock(amount="100.00", currency="GBP"),
        )
    ]
    mock_cli.client.get_account_balances = Mock(return_value=mock_balance)
    mock_select.return_value.ask.return_value = "balance"

    mock_cli._show_account_menu(account)

    mock_cli.client.get_account_balances.assert_called_once_with("ACC1")


@patch("beancount_gocardless.cli.questionary.select")
@patch("beancount_gocardless.cli.questionary.confirm")
def test_show_account_menu_delete_link(mock_confirm, mock_select, mock_cli):
    """Test _show_account_menu with delete action."""
    account = {
        "id": "ACC1",
        "name": "Test Account",
        "iban": "GB123",
        "institution_id": "BANK1",
        "requisition_reference": "ref1",
    }

    mock_select.return_value.ask.return_value = "delete"
    mock_confirm.return_value.ask.return_value = True

    mock_req = Mock()
    mock_req.id = "REQ1"
    mock_cli.client.find_requisition_by_reference = Mock(return_value=mock_req)
    mock_cli.client.delete_requisition = Mock()

    mock_cli._show_account_menu(account)


@patch("beancount_gocardless.cli.questionary.select")
def test_show_account_menu_back(mock_select, mock_cli):
    """Test _show_account_menu with back action."""
    account = {
        "id": "ACC1",
        "name": "Test Account",
        "iban": "GB123",
        "institution_id": "BANK1",
        "requisition_reference": "ref1",
    }

    mock_select.return_value.ask.return_value = "back"
    mock_cli._show_account_menu(account)


def test_view_balance_success(mock_cli):
    """Test _view_balance with successful response."""
    mock_balance = Mock()
    mock_balance.balances = [
        Mock(
            balance_type="closingAvailable",
            balance_amount=Mock(amount="100.00", currency="GBP"),
        ),
        Mock(
            balance_type="openingBooked",
            balance_amount=Mock(amount="50.00", currency="GBP"),
        ),
    ]
    mock_cli.client.get_account_balances = Mock(return_value=mock_balance)

    mock_cli._view_balance("ACC1")

    mock_cli.client.get_account_balances.assert_called_once_with("ACC1")


def test_view_balance_error(mock_cli):
    """Test _view_balance with error response."""
    mock_cli.client.get_account_balances = Mock(side_effect=Exception("API Error"))

    mock_cli._view_balance("ACC1")

    mock_cli.client.get_account_balances.assert_called_once_with("ACC1")


@patch("beancount_gocardless.cli.questionary.confirm")
def test_delete_link_success(mock_confirm, mock_cli):
    """Test _delete_link with successful deletion."""
    cli = CLI(
        secret_id="test-id",
        secret_key="test-key",
        mock=False,
    )

    mock_req = Mock()
    mock_req.id = "REQ1"
    cli.client.find_requisition_by_reference = Mock(return_value=mock_req)
    cli.client.delete_requisition = Mock()

    mock_confirm.return_value.ask.return_value = True

    cli._delete_link("ref1")

    cli.client.find_requisition_by_reference.assert_called_once_with("ref1")
    cli.client.delete_requisition.assert_called_once_with("REQ1")


@patch("beancount_gocardless.cli.questionary.confirm")
def test_delete_link_cancelled(mock_confirm, mock_cli):
    """Test _delete_link when user cancels."""
    cli = CLI(
        secret_id="test-id",
        secret_key="test-key",
        mock=False,
    )

    mock_confirm.return_value.ask.return_value = False

    cli._delete_link("ref1")


def test_delete_link_mock_mode(mock_cli):
    """Test _delete_link shows error in mock mode."""
    mock_cli._delete_link("ref1")


@patch("beancount_gocardless.cli.questionary.autocomplete")
def test_select_country(mock_autocomplete, mock_cli):
    """Test _select_country with common country."""
    mock_autocomplete.return_value.ask.return_value = "France"

    result = mock_cli._select_country()

    assert result == "FR"


@patch("beancount_gocardless.cli.questionary.autocomplete")
@patch("beancount_gocardless.cli.questionary.text")
def test_select_country_other(mock_text, mock_autocomplete, mock_cli):
    """Test _select_country with 'other' option."""
    mock_autocomplete.return_value.ask.return_value = "Other (enter code)"
    mock_text.return_value.ask.return_value = "US"

    result = mock_cli._select_country()

    assert result == "US"


@patch("beancount_gocardless.cli.questionary.autocomplete")
def test_select_country_back(mock_autocomplete, mock_cli):
    """Test _select_country with back option."""
    mock_autocomplete.return_value.ask.return_value = None

    result = mock_cli._select_country()

    assert result is None


@patch("beancount_gocardless.cli.questionary.autocomplete")
def test_select_bank(mock_autocomplete, mock_cli):
    """Test _select_bank with institutions."""
    mock_inst = Mock()
    mock_inst.name = "Test Bank"
    mock_inst.bic = "TESTBIC"
    mock_inst.id = "BANK1"
    mock_cli.client.get_institutions = Mock(return_value=[mock_inst])

    mock_autocomplete.return_value.ask.return_value = "Test Bank (BIC: TESTBIC)"

    result = mock_cli._select_bank("FR")

    assert result == mock_inst
    mock_cli.client.get_institutions.assert_called_once_with("FR")


def test_select_bank_no_institutions(mock_cli):
    """Test _select_bank when no institutions found."""
    mock_cli.client.get_institutions = Mock(return_value=[])

    result = mock_cli._select_bank("XX")

    assert result is None


def test_select_bank_error(mock_cli):
    """Test _select_bank with API error."""
    mock_cli.client.get_institutions = Mock(side_effect=Exception("API Error"))

    result = mock_cli._select_bank("FR")

    assert result is None


def test_create_bank_link_success():
    """Test _create_bank_link with successful creation."""
    cli = CLI(
        secret_id="test-id",
        secret_key="test-key",
        mock=False,
    )

    cli.client.find_requisition_by_reference = Mock(return_value=None)
    cli.client.create_bank_link = Mock(return_value="http://auth-link.com")

    cli._create_bank_link("my-ref", "BANK1")

    cli.client.find_requisition_by_reference.assert_called_once_with("my-ref")
    cli.client.create_bank_link.assert_called_once_with("my-ref", "BANK1")


def test_create_bank_link_already_exists():
    """Test _create_bank_link when reference already exists."""
    cli = CLI(
        secret_id="test-id",
        secret_key="test-key",
        mock=False,
    )

    mock_req = Mock()
    cli.client.find_requisition_by_reference = Mock(return_value=mock_req)

    cli._create_bank_link("my-ref", "BANK1")

    cli.client.find_requisition_by_reference.assert_called_once_with("my-ref")


def test_create_bank_link_error():
    """Test _create_bank_link with API error."""
    cli = CLI(
        secret_id="test-id",
        secret_key="test-key",
        mock=False,
    )

    cli.client.find_requisition_by_reference = Mock(side_effect=Exception("API Error"))

    cli._create_bank_link("my-ref", "BANK1")


@patch("beancount_gocardless.cli.questionary.select")
def test_add_account_mock_mode(mock_select, mock_cli):
    """Test add_account_interactive shows error in mock mode."""
    mock_cli.add_account_interactive()


@patch("beancount_gocardless.cli.questionary.select")
@patch("beancount_gocardless.cli.questionary.text")
def test_run_exit(mock_text, mock_select, mock_cli):
    """Test run method with exit choice."""
    mock_select.return_value.ask.return_value = "exit"

    mock_cli.run()


@patch("beancount_gocardless.cli.questionary.select")
def test_run_list_accounts(mock_select, mock_cli):
    """Test run method with list accounts choice."""
    mock_select.return_value.ask.side_effect = ["list", "exit"]

    mock_cli.list_accounts_interactive = Mock()

    mock_cli.run()

    mock_cli.list_accounts_interactive.assert_called_once()


@patch("beancount_gocardless.cli.questionary.select")
@patch("beancount_gocardless.cli.questionary.text")
def test_run_add_account(mock_text, mock_select, mock_cli):
    """Test run method with add account choice."""
    mock_select.return_value.ask.side_effect = ["add", "exit"]

    mock_cli.add_account_interactive = Mock()

    mock_cli.run()

    mock_cli.add_account_interactive.assert_called_once()
