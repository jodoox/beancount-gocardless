import os
import sys
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Button, Static, Input, Label
from textual.message import Message
from textual.binding import Binding
from rich.table import Table
from rich.text import Text
from typing import Optional
from beancount_gocardless.client import GoCardlessClient
from requests.exceptions import HTTPError as HttpServiceException
import logging

logger = logging.getLogger(__name__)


class ActionMessage(Message):
    """Custom message to signal actions within the TUI."""

    def __init__(self, action: str, payload: dict = None) -> None:
        super().__init__()
        self.action = action
        self.payload = payload or {}


class MenuView(Static):
    """Main menu view."""

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("GoCardLess TUI - Main Menu", id="title"),
            Button("List Banks", id="list_banks", variant="primary"),
            Button("List Linked Accounts", id="list_accounts", variant="primary"),
            Button("Get Account Balance", id="get_balance", variant="primary"),
            Button("Create New Link", id="create_link", variant="success"),
            Button("Delete Existing Link", id="delete_link", variant="error"),
            Button("Quit", id="quit", variant="default"),
            id="menu_view_vertical",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.post_message(ActionMessage(event.button.id))


class BaseSubView(Static):
    """Base class for sub-views with a back button."""

    def compose(self) -> ComposeResult:
        yield Vertical(
            self.compose_content(),
            Button("Back to Menu", id="back_to_menu", classes="back_button"),
        )

    def compose_content(self) -> ComposeResult:
        # To be overridden by subclasses
        yield Static("Content goes here")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back_to_menu":
            self.post_message(ActionMessage("show_menu"))
        else:
            # Allow subclasses to handle other buttons
            pass


class BanksView(BaseSubView):
    """View to display list of banks with country and name filtering."""

    def __init__(self, client: GoCardlessClient, country: Optional[str] = None):
        super().__init__()
        self.client = client
        self.country = country
        self.all_banks = None  # Store all banks
        self.status_message = Static("Loading banks...", id="banks_status_message")
        self.banks_table = Static("", id="banks_table")

    def compose_content(self) -> ComposeResult:
        yield Label("Banks", classes="view_title")
        yield Input(placeholder="Filter banks by name...", id="bank_filter_input")
        yield Input(
            value=self.country,
            placeholder="Country (e.g. FR)",
            id="country_filter_input",
            max_length=2,
        )
        yield self.status_message
        yield ScrollableContainer(
            self.banks_table,
            id="banks_scrollable_area",
            classes="horizontal-scroll",
        )
        yield Button("Back to Menu", id="back_to_menu", classes="back_button")

    # Override the base class compose to avoid duplicate back button
    def compose(self) -> ComposeResult:
        yield Vertical(
            *self.compose_content(),
            id="banks_view_vertical",
        )

    async def on_mount(self) -> None:
        """Load all banks on mount."""
        await self.filter_banks("", "")

    async def filter_banks(
        self, name_filter: Optional[str] = "", country_code: Optional[str] = None
    ) -> None:
        """Filters the banks based on current country and name filter."""
        try:
            if not self.all_banks:
                self.status_message.update("Loading all banks...")
                self.all_banks = self.client.list_banks(country=None)

            self.banks_table.update(
                f"Loading accounts... {name_filter} {country_code} {len(self.all_banks)}"
            )

            name_filtered = [
                b
                for b in self.all_banks
                if (name_filter.upper() in b.get("name", "").upper() or not name_filter)
                and (country_code in b.get("countries", []) or not country_code)
            ]

            if not name_filtered:
                filter_msg = f" matching '{name_filter}'" if name_filter else ""
                self.banks_table.update(
                    f"No banks found in {country_code}{filter_msg}. Total: {len(self.all_banks)} available."
                )
                self.status_message.update("")
                return

            # Create a formatted table for display
            table = Table(title=None, expand=True, min_width=80)
            table.add_column("Name", overflow="ellipsis", min_width=30)
            table.add_column("ID", overflow="ellipsis", min_width=20)
            table.add_column("Countries", overflow="ellipsis", min_width=15)

            for bank in name_filtered:
                countries = ", ".join(bank.get("countries", []))
                table.add_row(bank.get("name", "N/A"), bank.get("id", "N/A"), countries)

            # Update the table content
            self.banks_table.update(table)
            self.status_message.update(f"Showing {len(name_filtered)} banks")

        except Exception as e:
            self.status_message.update(
                Text(f"Error filtering banks: {e}", style="bold red")
            )

    async def on_input_changed(self, event: Input.Changed) -> None:
        """Event handler for input changes in either filter input."""
        input_id = event.input.id
        if input_id in ["country_filter_input", "bank_filter_input"]:
            name_input = self.query_one("#bank_filter_input", Input)
            country_input = self.query_one("#country_filter_input", Input)
            country_code = country_input.value.upper()
            omit_country = len(country_code) != 2

            await self.filter_banks(
                name_filter=name_input.value,
                country_code=country_code if not omit_country else None,
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses within this view."""
        if event.button.id == "back_to_menu":
            self.post_message(ActionMessage("show_menu"))


class AccountsView(BaseSubView):
    """View to display linked accounts with complete information."""

    def __init__(self, client: GoCardlessClient):
        super().__init__()
        self.client = client
        self.status_message = Static(
            "Loading accounts...", id="accounts_status_message"
        )
        self.accounts_table = Static("", id="accounts_table")

    def compose_content(self) -> ComposeResult:
        yield Label("Linked Accounts", classes="view_title")
        yield self.status_message
        yield ScrollableContainer(
            self.accounts_table,
            id="accounts_scrollable_area",
            classes="horizontal-scroll",
        )
        yield Button("Back to Menu", id="back_to_menu", classes="back_button")

    # Override the base class compose to avoid duplicate back button
    def compose(self) -> ComposeResult:
        yield Vertical(
            *self.compose_content(),
            id="accounts_view_vertical",
        )

    async def on_mount(self) -> None:
        await self.load_accounts()

    async def load_accounts(self) -> None:
        """Loads and displays the linked accounts with detailed information."""
        try:
            self.status_message.update("Loading accounts...")
            accounts = self.client.list_accounts()
            if not accounts:
                self.accounts_table.update("No accounts found.")
                self.status_message.update("")
                return

            # Create a formatted table for display
            table = Table(title=None, expand=True, min_width=100)
            table.add_column("#", style="dim", width=3)
            table.add_column("Bank", overflow="ellipsis", min_width=20)
            table.add_column("Name", overflow="crop", min_width=20)
            table.add_column("ID", overflow="ellipsis", min_width=20)
            table.add_column("IBAN", overflow="ellipsis", min_width=20)
            table.add_column("Reference", overflow="ellipsis", min_width=15)
            table.add_column("Status", width=6)
            table.add_column("Last Accessed", min_width=12)

            # Format and add accounts to the table
            for idx, account in enumerate(accounts, start=1):
                # import pdb
                # pdb.set_trace()
                # Get values with fallbacks for any missing keys
                institution_id = account.get("institution_id", "N/A")
                name = account.get("name", account.get("owner_name", "N/A"))
                iban = account.get("iban", "N/A")
                account_id = account.get("account_id", "N/A")
                reference = account.get("reference", "N/A")
                status = account.get("status", "N/A")
                last_accessed = account.get("last_accessed", "")
                if last_accessed:
                    try:
                        last_accessed = last_accessed.split("T")[0]
                    except Exception:
                        pass

                table.add_row(
                    str(idx),
                    institution_id,
                    name,
                    account_id,
                    iban,
                    reference,
                    status,
                    last_accessed,
                )

            # Update the table content
            self.accounts_table.update(table)
            self.status_message.update("")

        except HttpServiceException as e:
            self.status_message.update(Text(f"API Error: {e}", style="bold red"))
        except Exception as e:
            self.status_message.update(Text(f"Unexpected error: {e}", style="bold red"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses within this view."""
        if event.button.id == "back_to_menu":
            self.post_message(ActionMessage("show_menu"))


# ... existing code ...


class BalanceView(BaseSubView):
    """View to get and display account balance."""

    def __init__(
        self, client: "GoCardlessClient"
    ):  # Forward reference GoCardlessClient if not imported yet
        super().__init__()
        self.client = client
        self.accounts_data = []

    def compose(self) -> ComposeResult:
        """Override compose to yield widgets from compose_content."""
        for widget in self.compose_content():
            yield widget

    def compose_content(self) -> ComposeResult:
        yield Label("Account Balance", classes="view_title")
        # Moved status message to be a direct child of BalanceView, and sibling to content_area
        yield Static(
            "", id="balance_status_message"
        )  # Initialize empty or with a generic placeholder
        yield Vertical(
            # The initial Static message that was here is removed
            id="balance_content_area",
        )

    async def on_mount(self) -> None:
        # Query elements only after they are mounted
        content_area = self.query_one("#balance_content_area", Vertical)
        status_message = self.query_one("#balance_status_message", Static)
        status_message.update(
            "Loading accounts for selection..."
        )  # Set initial operational message
        await self.load_accounts_for_selection(content_area, status_message)

    async def load_accounts_for_selection(
        self, content_area: Vertical, status_message: Static
    ):
        try:
            # status_message.update("Loading accounts...") # Message set by on_mount or can be refined here
            self.accounts_data = self.client.list_accounts()
            await (
                content_area.remove_children()
            )  # Clear "Loading..." or previous content from content_area

            if not self.accounts_data:
                await content_area.mount(
                    Static("No accounts linked. Cannot fetch balance.")
                )
                status_message.update(
                    "No accounts available to display."
                )  # Update persistent status
                return

            table = Table(title="Select Account by Index for Balance", expand=True)
            table.add_column("#", style="dim")
            table.add_column("Name", overflow="fold")
            table.add_column("Institution ID", overflow="fold")
            for idx, a in enumerate(self.accounts_data):
                table.add_row(str(idx), a["name"], a["institution_id"])

            await content_area.mount(table)  # Mount Table widget directly
            idx_input = Input(
                placeholder="Enter account # and press Enter", id="acct_idx_input"
            )
            await content_area.mount(idx_input)
            idx_input.focus()
            status_message.update(
                "Please select an account from the list."
            )  # Clear or update status message
        except HttpServiceException as e:  # Make sure HttpServiceException is defined
            status_message.update(
                Text(f"Error loading accounts: {e}", style="bold red")
            )
            await content_area.remove_children()
            await content_area.mount(
                Static(
                    Text(
                        "Failed to load accounts. Check connection or try again later.",
                        style="yellow",
                    )
                )
            )
        except Exception as e:
            status_message.update(Text(f"Unexpected error: {e}", style="bold red"))
            await content_area.remove_children()
            await content_area.mount(
                Static(
                    Text(
                        "An unexpected error occurred while loading accounts.",
                        style="yellow",
                    )
                )
            )

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "acct_idx_input":
            content_area = self.query_one("#balance_content_area", Vertical)
            # status_message is now persistent and queried once
            status_message = self.query_one("#balance_status_message", Static)

            await (
                content_area.remove_children()
            )  # Clear account list and input from content_area

            try:
                idx = int(event.value)
                if not (0 <= idx < len(self.accounts_data)):
                    # Display temporary error message in content_area
                    await content_area.mount(
                        Static(Text("Invalid account index.", style="bold red"))
                    )
                    status_message.update(
                        Text(
                            "Selection out of range. Please try again.", style="yellow"
                        )
                    )
                    # Reload account selection UI
                    await self.load_accounts_for_selection(content_area, status_message)
                    return

                account_to_check = self.accounts_data[idx]
                acct_id = account_to_check["account_id"]

                status_message.update(
                    f"Fetching balances for {account_to_check['name']} ({acct_id})..."
                )
                # Optionally, display a "Fetching..." message in content_area as well
                await content_area.mount(Static("Fetching balances..."))

                balances_data = self.client.get_balances(account_id=acct_id)
                await content_area.remove_children()  # Clear "Fetching..." message

                table = Table(
                    title=f"Balances for {account_to_check['name']}", expand=True
                )
                table.add_column("Type", overflow="fold")
                table.add_column("Amount")
                table.add_column("Currency")
                if "balances" in balances_data and balances_data["balances"]:
                    for b in balances_data["balances"]:
                        balance_amount_info = b.get("balanceAmount", {})
                        table.add_row(
                            b.get("balanceType", "N/A"),
                            str(balance_amount_info.get("amount", "N/A")),
                            balance_amount_info.get("currency", "N/A"),
                        )
                else:
                    table.add_row("N/A", "No balance data found", "N/A")

                await content_area.mount(table)  # Mount the results table
                status_message.update(
                    f"Balances for {account_to_check['name']} displayed."
                )
                # Consider how the user navigates back to account selection (e.g., a button, or re-selecting the view)

            except ValueError:
                # Display temporary error message in content_area
                await content_area.mount(
                    Static(
                        Text("Invalid input. Please enter a number.", style="bold red")
                    )
                )
                status_message.update(
                    Text("Numeric input required for account index.", style="yellow")
                )
                await self.load_accounts_for_selection(
                    content_area, status_message
                )  # Reload selection
            except (
                HttpServiceException
            ) as e:  # Make sure HttpServiceException is defined
                status_message.update(
                    Text(f"API Error fetching balances: {e}", style="bold red")
                )
                await content_area.mount(
                    Static(
                        Text(
                            "Could not retrieve balances due to an API error.",
                            style="red",
                        )
                    )
                )
                # Optionally, reload selection UI so user can try again or select a different account
                # await self.load_accounts_for_selection(content_area, status_message)
            except Exception as e:
                status_message.update(
                    Text(f"Error processing balance request: {e}", style="bold red")
                )
                await content_area.mount(
                    Static(
                        Text(
                            "An unexpected error occurred while fetching balances.",
                            style="red",
                        )
                    )
                )
                # Optionally, reload selection UI
                # await self.load_accounts_for_selection(content_area, status_message)


class LinkView(BaseSubView):
    """View to create a new bank link."""

    def __init__(self, client: GoCardlessClient):
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        """Override compose to yield widgets from compose_content."""
        for widget in self.compose_content():
            yield widget

    def compose_content(self) -> ComposeResult:
        yield Label("Create New Bank Link", classes="view_title")
        yield Vertical(
            Input(
                placeholder="Bank ID (e.g., SANDBOXFINANCE_SFIN0000)",
                id="bank_id_input",
            ),
            Input(
                placeholder="Unique Reference (e.g., mypc-savings-ref)", id="ref_input"
            ),
            Button("Create Link", id="do_create_link_button", variant="success"),
            Static(id="link_result_message", classes="result_message_area"),
            id="link_form_area",
        )

    async def on_mount(self) -> None:
        await self.query_one("#bank_id_input", Input).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back_to_menu":
            self.post_message(ActionMessage("show_menu"))
        elif event.button.id == "do_create_link_button":
            await self.process_create_link()

    async def process_create_link(self) -> None:
        bank_input = self.query_one("#bank_id_input", Input)
        ref_input = self.query_one("#ref_input", Input)
        result_message_widget = self.query_one("#link_result_message", Static)
        create_button = self.query_one("#do_create_link_button", Button)

        bank_id = bank_input.value.strip()
        reference = ref_input.value.strip()

        if not bank_id or not reference:
            result_message_widget.update(
                Text("Bank ID and Reference are required.", style="bold red")
            )
            return

        try:
            bank_input.disabled = True
            ref_input.disabled = True
            create_button.disabled = True
            result_message_widget.update("Creating link...")

            link_info = self.client.create_link(reference, bank_id)  # API call

            msg_parts = [
                Text(f"Status: {link_info.get('status', 'N/A')}\n", style="bold")
            ]
            if link_info.get("message"):
                msg_parts.append(Text(f"Message: {link_info['message']}\n"))
            if link_info.get("link"):
                msg_parts.append(
                    Text(
                        "Link URL (copy and open in browser to authorize):\n",
                        style="bold yellow",
                    )
                )
                msg_parts.append(Text(f"{link_info['link']}", style="underline blue"))

            result_message_widget.update(Text.assemble(*msg_parts))

        except HttpServiceException as e:
            result_message_widget.update(Text(f"API Error:\n{e}", style="bold red"))
        except Exception as e:
            result_message_widget.update(
                Text(f"Unexpected Error:\n{e}", style="bold red")
            )
        finally:
            bank_input.disabled = False
            ref_input.disabled = False
            create_button.disabled = False


class DeleteLinkView(BaseSubView):
    """View to delete an existing bank link."""

    def __init__(self, client: GoCardlessClient):
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        """Override compose to yield widgets from compose_content."""
        for widget in self.compose_content():
            yield widget

    def compose_content(self) -> ComposeResult:
        yield Label("Delete Existing Link", classes="view_title")
        yield Vertical(
            Input(placeholder="Reference of link to delete", id="del_ref_input"),
            Button("Delete Link", id="do_delete_link_button", variant="error"),
            Static(id="delete_link_result_message", classes="result_message_area"),
            id="delete_link_form_area",
        )

    async def on_mount(self) -> None:
        await self.query_one("#del_ref_input", Input).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back_to_menu":
            self.post_message(ActionMessage("show_menu"))
        elif event.button.id == "do_delete_link_button":
            await self.process_delete_link()

    async def process_delete_link(self) -> None:
        ref_input = self.query_one("#del_ref_input", Input)
        result_message_widget = self.query_one("#delete_link_result_message", Static)
        delete_button = self.query_one("#do_delete_link_button", Button)

        reference = ref_input.value.strip()

        if not reference:
            result_message_widget.update(
                Text("Reference is required to delete a link.", style="bold red")
            )
            return

        try:
            ref_input.disabled = True
            delete_button.disabled = True
            result_message_widget.update(
                f"Deleting link with reference '{reference}'..."
            )

            response = self.client.delete_link(reference)  # API call

            style = (
                "bold green" if response.get("status") == "deleted" else "bold yellow"
            )
            result_message_widget.update(
                Text(
                    f"Status: {response.get('status', 'N/A')}\nMessage: {response.get('message', 'N/A')}",
                    style=style,
                )
            )

        except HttpServiceException as e:
            result_message_widget.update(Text(f"API Error:\n{e}", style="bold red"))
        except Exception as e:
            result_message_widget.update(
                Text(f"Unexpected Error:\n{e}", style="bold red")
            )
        finally:
            ref_input.disabled = False
            delete_button.disabled = False


class GoCardLessApp(App):
    TITLE = "GoCardLess API TUI"
    CSS = """
    Screen {
        align: center middle;
    }
    #app_container {
        width: 100%;
        max-width: 300; /* Max width for the main content container */
        height: auto;
        border: round $primary;
        padding: 1 2;
    }
    #title { /* For MenuView title */
        width: 100%;
        text-align: center;
        padding: 1 0 2 0;
        text-style: bold;
    }
    .view_title { /* For sub-view titles */
        width: 100%;
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold underline;
    }
    #menu_view_vertical > Button {
        width: 100%;
        margin-bottom: 1;
    }
    .back_button {
        width: 100%;
        margin-top: 2;
    }
    Input, Button { /* General spacing for inputs and buttons in forms */
        margin-bottom: 1;
    }
    .result_message_area {
        margin-top: 1;
        padding: 1;
        border: round $primary-background-darken-2;
        min-height: 3;
        width: 100%;
    }
    Vertical { /* Ensure vertical containers take full width by default */
        width: 100%;
    }
    Table {
        margin-top: 1;
    }
    """
    BINDINGS = [
        Binding("q", "quit", "Quit App", show=True, priority=True),
        Binding(
            "escape", "show_menu_escape", "Back to Menu", show=True
        ),  # Fixed: Always show, we'll control visibility elsewhere
    ]

    def __init__(self, secret_id=None, secret_key=None):
        super().__init__()
        sid = secret_id or os.getenv("GOCARDLESS_SECRET_ID")
        sk = secret_key or os.getenv("GOCARDLESS_SECRET_KEY")
        if not sid or not sk:
            logger.error(
                "Error: GoCardLess credentials (GOCARDLESS_SECRET_ID, GOCARDLESS_SECRET_KEY) not found.",
            )
            logger.error(
                "Please set them as environment variables or pass via arguments (not implemented in this TUI version).",
            )
            sys.exit(1)  # Exit if no creds
        self.client = GoCardlessClient(sid, sk, {})
        self._current_view_is_menu = True

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(MenuView(), id="app_container")
        yield Footer()

    async def on_mount(self) -> None:
        # Fixed: removed the call to update_escape_binding since we're showing escape binding always
        # and managing its behavior in action_show_menu_escape
        pass

    async def switch_view(self, new_view_widget: Static) -> None:
        container = self.query_one("#app_container", Container)
        await container.remove_children()
        await container.mount(new_view_widget)
        self._current_view_is_menu = isinstance(new_view_widget, MenuView)

    async def action_show_menu_escape(self) -> None:
        """Handle Escape key press to go back to menu."""
        if not self._current_view_is_menu:
            await self.switch_view(MenuView())

    async def on_action_message(self, msg: ActionMessage) -> None:
        action_to_view_map = {
            "show_menu": MenuView,
            "list_banks": lambda: BanksView(self.client),
            "list_accounts": lambda: AccountsView(self.client),
            "get_balance": lambda: BalanceView(self.client),
            "create_link": lambda: LinkView(self.client),
            "delete_link": lambda: DeleteLinkView(self.client),
        }

        if msg.action == "quit":
            self.exit()
            return

        if msg.action in action_to_view_map:
            view_constructor = action_to_view_map[msg.action]
            new_view = view_constructor()
            await self.switch_view(new_view)
        else:
            # Fallback for unknown action, though should not happen with defined buttons
            container = self.query_one("#app_container", Container)
            await container.remove_children()
            await container.mount(
                Static(Text(f"Unknown action: {msg.action}", style="bold red"))
            )
            self._current_view_is_menu = False  # Assuming it's not menu


logger.info(os.getenv("GOCARDLESS_SECRET_ID"), os.getenv("GOCARDLESS_SECRET_KEY"))


def main():
    # For this TUI, credentials must be set as environment variables
    # GOCARDLESS_SECRET_ID and GOCARDLESS_SECRET_KEY
    if not os.getenv("GOCARDLESS_SECRET_ID") or not os.getenv("GOCARDLESS_SECRET_KEY"):
        logger.error(
            "Error: GOCARDLESS_SECRET_ID and GOCARDLESS_SECRET_KEY environment variables must be set.",
        )
        sys.exit(1)

    app = GoCardLessApp()
    app.run()


# if __name__ == "__main__":
# main()
