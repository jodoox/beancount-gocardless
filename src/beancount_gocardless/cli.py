"""Interactive CLI for managing GoCardless bank connections.

Provides commands to list accounts, add new bank links, and browse
institutions. Uses rich for output and questionary for interactive prompts.
"""

from typing import Optional, Union
from datetime import datetime
import os
import sys
import argparse

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box
import questionary

from .client import GoCardlessClient
from .mock_client import MockGoCardlessClient
from .models import AccountInfo, Institution
from .utils import load_dotenv

__all__ = ["CLI", "main"]


class CLI:
    """Interactive CLI for managing GoCardless bank connections."""

    def __init__(
        self,
        secret_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        mock: bool = False,
        env_file: Optional[str] = None,
    ):
        self.console = Console()
        self.mock = mock

        if env_file:
            load_dotenv(env_file)

        self.secret_id = secret_id or os.getenv("GOCARDLESS_SECRET_ID")
        self.secret_key = secret_key or os.getenv("GOCARDLESS_SECRET_KEY")
        self._init_client()

    def _init_client(self) -> None:
        """Initialize the GoCardless client (real or mock)."""
        if self.mock:
            self.console.print("[dim]Using mock client[/dim]")
            self.client: Union[GoCardlessClient, MockGoCardlessClient] = (
                MockGoCardlessClient(
                    "mock-id",
                    "mock-key",
                )
            )
        else:
            if not self.secret_id or not self.secret_key:
                self.console.print(
                    "[red]Error: Secret ID and Secret Key are required[/red]\n"
                    "Set GOCARDLESS_SECRET_ID and GOCARDLESS_SECRET_KEY environment variables\n"
                    "or pass --secret-id and --secret-key arguments."
                )
                sys.exit(1)
            self.client = GoCardlessClient(self.secret_id, self.secret_key)

    def _print_header(self, title: str) -> None:
        """Print a styled header."""
        self.console.print()
        self.console.print(
            Panel(
                Text(title, style="bold"),
                box=box.ROUNDED,
                border_style="blue",
            )
        )
        self.console.print()

    def _print_success(self, message: str) -> None:
        """Print a success message."""
        self.console.print(f"[green]✓[/green] {message}")

    def _print_error(self, message: str) -> None:
        """Print an error message."""
        self.console.print(f"[red]✗[/red] {message}")

    def _print_info(self, message: str) -> None:
        """Print an info message."""
        self.console.print(f"[dim]{message}[/dim]")

    def _format_expiry_status(self, account: AccountInfo) -> str:
        """Format expiry status for display in account list."""
        is_expired = account.get("is_expired", False)
        if is_expired:
            return "[EXPIRED]"

        access_valid_until = account.get("access_valid_until")
        if access_valid_until:
            try:
                expiry = datetime.fromisoformat(
                    access_valid_until.replace("Z", "+00:00")
                )
                days_remaining = (expiry - datetime.now(expiry.tzinfo)).days
                if days_remaining <= 7 and days_remaining >= 0:
                    return f"[{days_remaining}d left]"
            except (ValueError, TypeError):
                pass
        return ""

    def _show_expiry_details(self, account: AccountInfo) -> None:
        """Show detailed expiry information in a table."""
        access_valid_until = account.get("access_valid_until")
        is_expired = account.get("is_expired", False)
        status = account.get("requisition_status", "Unknown")

        table = Table(box=box.ROUNDED, show_header=False, border_style="blue")
        table.add_column("Property", style="cyan")
        table.add_column("Value")

        table.add_row("Status", status)

        if access_valid_until:
            try:
                expiry = datetime.fromisoformat(
                    access_valid_until.replace("Z", "+00:00")
                )
                days_remaining = (expiry - datetime.now(expiry.tzinfo)).days
                expiry_str = expiry.strftime("%Y-%m-%d %H:%M")

                if is_expired:
                    table.add_row("Access", f"[red]Expired on {expiry_str}[/red]")
                elif days_remaining < 0:
                    table.add_row("Access", "[green]Valid[/green]")
                elif days_remaining <= 7:
                    table.add_row(
                        "Access",
                        f"[yellow]Expires in {days_remaining} days ({expiry_str})[/yellow]",
                    )
                else:
                    table.add_row(
                        "Access",
                        f"[green]Valid until {expiry_str} ({days_remaining} days left)[/green]",
                    )
            except (ValueError, TypeError):
                table.add_row("Access", "Unknown")
        else:
            table.add_row("Access", "Not available")

        self.console.print(table)

    def run(self) -> None:
        """Main entry point for the interactive CLI."""
        self._print_header("GoCardless Bank Manager")

        while True:
            action = questionary.select(
                "What would you like to do?",
                choices=[
                    questionary.Choice("List accounts", value="list"),
                    questionary.Choice("Add account", value="add"),
                    questionary.Choice("List banks (browse)", value="banks"),
                    questionary.Choice("Exit", value="exit"),
                ],
                pointer=">",
            ).ask()

            if action is None or action == "exit":
                self.console.print("\n[dim]Goodbye![/dim]")
                break

            try:
                if action == "list":
                    self.list_accounts_interactive()
                elif action == "add":
                    self.add_account_interactive()
                elif action == "banks":
                    self.list_banks_interactive()
            except KeyboardInterrupt:
                self.console.print("\n[dim]Cancelled[/dim]")
                continue
            except Exception as e:
                self._print_error(f"Error: {e}")
                continue

            self.console.print()
            continue_choice = questionary.select(
                "What next?",
                choices=[
                    questionary.Choice("Continue", value="continue"),
                    questionary.Choice("Exit", value="exit"),
                ],
                default="continue",
                pointer=">",
            ).ask()

            if continue_choice == "exit":
                self.console.print("\n[dim]Goodbye![/dim]")
                break

    def list_accounts_interactive(self) -> None:
        """List all connected accounts with arrow-key selection."""
        self._print_header("Connected Accounts")

        accounts = self.client.list_accounts()

        if not accounts:
            self.console.print("[dim]No accounts found.[/dim]")
            return

        account_map: dict[str, dict] = {}
        choices: list[str] = []
        for acc in accounts:
            iban = acc.get("iban", "no-iban")
            name = acc.get("name", "no-name")
            institution = acc.get("institution_id", "unknown")
            expiry_status = self._format_expiry_status(acc)
            display = f"{institution} - {name} ({iban}){expiry_status}"
            account_map[display] = acc
            choices.append(display)

        choices.append("Back")

        selected = questionary.select(
            "Select an account:",
            choices=choices,
            pointer=">",
        ).ask()

        if selected is None or selected == "Back":
            return

        self._show_account_menu(account_map[selected])

    def _show_account_menu(self, account: AccountInfo) -> None:
        """Show the action menu for a selected account."""
        account_id = account.get("id", "unknown")
        iban = account.get("iban", "no-iban")
        name = account.get("name", "no-name")
        institution = account.get("institution_id", "unknown")
        requisition_ref = account.get("requisition_reference", "no-ref")
        is_expired = account.get("is_expired", False)

        self.console.print()
        table = Table(box=box.ROUNDED, show_header=False, border_style="blue")
        table.add_column("Property", style="cyan")
        table.add_column("Value")
        table.add_row("ID", account_id)
        table.add_row("Name", name)
        table.add_row("IBAN", iban)
        table.add_row("Institution", institution)
        table.add_row("Reference", requisition_ref)
        self.console.print(table)

        self._show_expiry_details(account)
        self.console.print()

        choices = [
            questionary.Choice("View balance", value="balance"),
        ]

        if is_expired:
            choices.append(questionary.Choice("[Renew connection]", value="renew"))

        choices.extend(
            [
                questionary.Choice("Delete link", value="delete"),
                questionary.Choice("← Back", value="back"),
            ]
        )

        action = questionary.select(
            "Choose an action:",
            choices=choices,
            pointer=">",
        ).ask()

        if action == "balance":
            self._view_balance(account_id)
        elif action == "renew":
            if institution:
                self._renew_connection(requisition_ref, institution)
            else:
                self._print_error("Cannot renew: institution ID not found")
        elif action == "delete":
            self._delete_link(requisition_ref)

    def _renew_connection(self, reference: str, institution_id: Optional[str]) -> None:
        if not institution_id:
            self._print_error("Cannot renew: institution ID not available")
            return

        if self.mock:
            self._print_error("Mock client does not support renewing connections")
            return

        confirm = questionary.confirm(
            "Create new authorization link to replace the expired one?",
            default=False,
        ).ask()

        if not confirm:
            self._print_info("Renewal cancelled")
            return

        try:
            old_req = self.client.find_requisition_by_reference(reference)
            if old_req:
                self.client.delete_requisition(old_req.id)
                self._print_success("Old expired link deleted")

            link = self.client.create_bank_link(reference, institution_id)

            if link:
                self._print_success("New bank link created!")
                self.console.print()
                self.console.print(
                    Panel(
                        f"[bold]Authorization Link:[/bold]\n\n{link}",
                        box=box.ROUNDED,
                        border_style="green",
                    )
                )
                self.console.print()
                self.console.print(
                    "[dim]Open this link in your browser to authorize the connection.[/dim]"
                )
            else:
                self._print_error("Could not create new bank link")

        except Exception as e:
            self._print_error(f"Error renewing connection: {e}")

    def _view_balance(self, account_id: str) -> None:
        """View balance for an account."""
        try:
            balances = self.client.get_account_balances(account_id)

            self.console.print()
            table = Table(
                title="Account Balances",
                box=box.ROUNDED,
                border_style="green",
            )
            table.add_column("Type", style="cyan")
            table.add_column("Amount", style="green")
            table.add_column("Currency")

            for balance in balances.balances:
                amount = balance.balance_amount.amount
                currency = balance.balance_amount.currency
                table.add_row(balance.balance_type, amount, currency)

            self.console.print(table)

        except Exception as e:
            self._print_error(f"Could not fetch balance: {e}")

    def _delete_link(self, reference: str) -> None:
        """Delete a bank link by reference."""
        if self.mock:
            self._print_error("Mock client does not support deleting links")
            return

        confirm = questionary.confirm(
            f"Are you sure you want to delete the link '{reference}'?",
            default=False,
        ).ask()

        if not confirm:
            self._print_info("Deletion cancelled")
            return

        try:
            req = self.client.find_requisition_by_reference(reference)
            if req:
                self.client.delete_requisition(req.id)
                self._print_success(f"Deleted link '{reference}'")
            else:
                self._print_error(f"No link found with reference '{reference}'")
        except Exception as e:
            self._print_error(f"Could not delete link: {e}")

    def list_banks_interactive(self) -> None:
        """List and browse available banks by country."""
        self._print_header("Browse Banks")

        country = self._select_country()
        if not country:
            return

        self._print_info(f"Loading banks for {country}...")

        try:
            institutions = self.client.get_institutions(country)
        except Exception as e:
            self._print_error(f"Could not load banks: {e}")
            return

        if not institutions:
            self._print_error(f"No banks found for country {country}")
            return

        choices = []
        for inst in institutions:
            display = f"{inst.name}"
            if inst.bic:
                display += f" (BIC: {inst.bic})"
            choices.append(questionary.Choice(display, value=inst))

        choices.append(questionary.Choice("← Back", value=None))

        self.console.print(f"\n[dim]Found {len(institutions)} banks.[/dim]\n")

        selected = questionary.select(
            "Select a bank to view details:",
            choices=choices,
            pointer=">",
        ).ask()

        if selected is None:
            return

        self._show_bank_details(selected)

    def _show_bank_details(self, institution: Institution) -> None:
        """Show details for a selected bank."""
        self.console.print()
        table = Table(box=box.ROUNDED, show_header=False, border_style="blue")
        table.add_column("Property", style="cyan")
        table.add_column("Value")
        table.add_row("Name", institution.name)
        table.add_row("ID", institution.id)
        table.add_row("BIC", institution.bic or "N/A")
        table.add_row(
            "Countries",
            ", ".join(institution.countries) if institution.countries else "N/A",
        )
        table.add_row("Transaction Days", institution.transaction_total_days or "N/A")
        self.console.print(table)
        self.console.print()

        action = questionary.select(
            "What would you like to do?",
            choices=[
                questionary.Choice("Create link for this bank", value="link"),
                questionary.Choice("← Back to bank list", value="back"),
            ],
            pointer=">",
        ).ask()

        if action == "link":
            reference = questionary.text(
                "Enter a unique reference for this connection:",
                default="my-bank",
            ).ask()
            if reference:
                self._create_bank_link(reference, institution.id)

    def add_account_interactive(self) -> None:
        """Add a new bank account interactively."""
        self._print_header("Add New Account")

        if self.mock:
            self._print_error("Mock client does not support adding accounts")
            return

        while True:
            country = self._select_country()
            if not country:
                return

            institution = self._select_bank(country)
            if institution is None:
                return

            reference = questionary.text(
                "Enter a unique reference for this connection:",
                default="my-bank",
            ).ask()

            if not reference:
                self._print_info("Cancelled")
                return

            self._create_bank_link(reference, institution.id)
            return

    def _select_country(self) -> Optional[str]:
        """Let user select a country from common options."""
        country_map = {
            "United Kingdom": "GB",
            "France": "FR",
            "Germany": "DE",
            "Spain": "ES",
            "Italy": "IT",
            "Netherlands": "NL",
            "Belgium": "BE",
            "Portugal": "PT",
            "Austria": "AT",
            "Ireland": "IE",
            "Other (enter code)": "other",
            "Back": None,
        }

        selected = questionary.autocomplete(
            "Select your country (type to filter):",
            choices=list(country_map.keys()),
            ignore_case=True,
        ).ask()

        if selected is None:
            return None

        value = country_map.get(selected)
        if value is None:
            return None

        if value == "other":
            country = questionary.text(
                "Enter 2-letter country code (e.g., US, CA, AU):",
            ).ask()
            return country.upper() if country else None

        return value

    def _select_bank(self, country: str) -> Optional[Institution]:
        """Search and select a bank for the given country."""
        self.console.print(f"\n[dim]Loading banks for {country}...[/dim]")

        try:
            institutions = self.client.get_institutions(country)
        except Exception as e:
            self._print_error(f"Could not load banks: {e}")
            return None

        if not institutions:
            self._print_error(f"No banks found for country {country}")
            return None

        bank_map: dict[str, Institution] = {}
        choices: list[str] = []
        for inst in institutions:
            display = f"{inst.name}"
            if inst.bic:
                display += f" (BIC: {inst.bic})"
            bank_map[display] = inst
            choices.append(display)

        choices.append("Back to country selection")

        self.console.print(f"\n[dim]Loaded {len(institutions)} banks[/dim]\n")

        selected = questionary.autocomplete(
            "Select your bank (type to filter by name or BIC):",
            choices=choices,
            ignore_case=True,
        ).ask()

        if selected is None or selected == "Back to country selection":
            return None

        return bank_map.get(selected)

    def _create_bank_link(self, reference: str, bank_id: str) -> None:
        """Create a bank link and display the authorization URL."""
        try:
            existing = self.client.find_requisition_by_reference(reference)
            if existing:
                self._print_error(f"A link with reference '{reference}' already exists")
                return

            link = self.client.create_bank_link(reference, bank_id)

            if link:
                self._print_success("Bank link created successfully!")
                self.console.print()
                self.console.print(
                    Panel(
                        f"[bold]Authorization Link:[/bold]\n\n{link}",
                        box=box.ROUNDED,
                        border_style="green",
                    )
                )
                self.console.print()
                self.console.print(
                    "[dim]Open this link in your browser to authorize the connection.[/dim]"
                )
                self.console.print(
                    "[dim]After authorization, your account will appear in the list.[/dim]"
                )
            else:
                self._print_error("Could not create bank link")

        except Exception as e:
            self._print_error(f"Error creating link: {e}")


def main():
    """Entry point for the interactive CLI."""
    parser = argparse.ArgumentParser(
        description="Interactive CLI for GoCardless Bank Account Data",
    )
    parser.add_argument(
        "--secret-id",
        default=os.getenv("GOCARDLESS_SECRET_ID"),
        help="API secret ID (defaults to env var GOCARDLESS_SECRET_ID)",
    )
    parser.add_argument(
        "--secret-key",
        default=os.getenv("GOCARDLESS_SECRET_KEY"),
        help="API secret key (defaults to env var GOCARDLESS_SECRET_KEY)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock client with fixture data (for testing)",
    )
    parser.add_argument(
        "--env-file",
        help="Path to a .env file to load environment variables from",
    )

    args = parser.parse_args()

    cli = CLI(
        secret_id=args.secret_id,
        secret_key=args.secret_key,
        mock=args.mock,
        env_file=args.env_file,
    )
    cli.run()


if __name__ == "__main__":
    main()
