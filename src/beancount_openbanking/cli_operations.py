"""Provider-specific CLI operations."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from .cli_support import DEFAULT_GOCARDLESS_REDIRECT_URL, render_table
from .providers import (
    EnableBankingProvider,
    GoCardlessProvider,
    Institution,
    Requisition,
)

__all__ = ["EnableBankingOperations", "GoCardlessOperations"]


class GoCardlessOperations:
    """Shared GoCardless command handlers."""

    def __init__(
        self,
        provider: GoCardlessProvider,
        console: Console | None = None,
    ) -> None:
        self.provider = provider
        self.console = console or Console()

    def list_accounts(self) -> None:
        rows = [
            [
                account.name or "",
                account.id,
                account.iban or "",
                str(account.provider_data.get("institution_id", "")),
                str(account.provider_data.get("requisition_reference", "")),
            ]
            for account in self.provider.list_accounts()
        ]
        render_table(
            self.console,
            "Accounts",
            ["Name", "Account ID", "IBAN", "Institution", "Reference"],
            rows,
            "No linked accounts.",
        )

    def list_banks(self, country: str | None = None, search: str | None = None) -> None:
        institutions = self.provider.list_institutions(country=country)
        if search:
            needle = search.lower()
            institutions = [
                institution
                for institution in institutions
                if needle in institution.name.lower()
                or needle in institution.id.lower()
                or needle in (institution.bic or "").lower()
            ]
        institutions.sort(key=lambda item: item.name.lower())
        rows = [
            [
                institution.name,
                institution.id,
                institution.bic or "",
                ", ".join(institution.countries),
                institution.transaction_total_days,
            ]
            for institution in institutions
        ]
        render_table(
            self.console,
            "Banks",
            ["Name", "Institution ID", "BIC", "Countries", "Days"],
            rows,
            "No banks found.",
        )

    def list_links(self) -> None:
        requisitions = sorted(
            self.provider.list_requisitions(),
            key=lambda item: item.created,
            reverse=True,
        )
        rows = [
            [
                item.reference,
                item.institution_id,
                item.status,
                str(len(item.accounts)),
                item.created,
                item.link or "",
            ]
            for item in requisitions
        ]
        render_table(
            self.console,
            "Bank Links",
            ["Reference", "Institution", "Status", "Accounts", "Created", "Link"],
            rows,
            "No bank links found.",
        )

    def delete_link(self, requisition_id: str) -> None:
        self.provider.delete_requisition(requisition_id)
        self.console.print(f"Deleted requisition {requisition_id}.")

    def create_link(
        self,
        institution_id: str,
        reference: str,
        redirect_url: str = DEFAULT_GOCARDLESS_REDIRECT_URL,
        user_language: str | None = None,
    ) -> Requisition:
        kwargs: dict[str, str] = {}
        if user_language:
            kwargs["user_language"] = user_language

        requisition = self.provider.create_requisition(
            redirect_url=redirect_url,
            institution_id=institution_id,
            reference=reference,
            **kwargs,
        )
        if requisition.link:
            self.console.print(Panel.fit(requisition.link, title="Authorization URL"))
        else:
            self.console.print(requisition.model_dump_json(indent=2))
        return requisition

    @staticmethod
    def format_institution_choice(institution: Institution) -> str:
        """Format an institution choice for interactive selection."""

        details = [institution.id]
        if institution.bic:
            details.append(institution.bic)
        return f"{institution.name} ({', '.join(details)})"


class EnableBankingOperations:
    """Shared Enable Banking command handlers."""

    def __init__(
        self,
        provider: EnableBankingProvider,
        console: Console | None = None,
    ) -> None:
        self.provider = provider
        self.console = console or Console()

    def list_accounts(self) -> None:
        rows = [
            [
                account.name or "",
                account.id,
                account.iban or "",
                account.currency or "",
            ]
            for account in self.provider.list_accounts()
        ]
        render_table(
            self.console,
            "Accounts",
            ["Name", "Account ID", "IBAN", "Currency"],
            rows,
            "No linked accounts.",
        )

    def list_banks(self, country: str, search: str | None = None) -> None:
        banks = self.provider.list_aspsps(country.upper())
        if search:
            needle = search.lower()
            banks = [
                bank
                for bank in banks
                if any(
                    needle in str(bank.get(key, "")).lower()
                    for key in ("name", "service_name", "uid", "bic")
                )
            ]
        banks.sort(key=lambda item: str(item.get("name", "")).lower())
        rows = [
            [
                str(bank.get("name", "")),
                str(bank.get("country", country.upper())),
                str(bank.get("uid", "")),
                str(bank.get("bic", "")),
            ]
            for bank in banks
        ]
        render_table(
            self.console,
            f"Banks ({country.upper()})",
            ["Name", "Country", "UID", "BIC"],
            rows,
            "No banks found.",
        )

    def list_links(self) -> None:
        sessions = self.provider.list_sessions()
        rows = []
        for session in sessions:
            aspsp = session.aspsp
            rows.append(
                [
                    session.session_id or "",
                    aspsp.name if aspsp else "",
                    aspsp.country if aspsp else "",
                    str(len(session.accounts)),
                    session.status or "",
                    session.authorized or "",
                ]
            )
        render_table(
            self.console,
            "Bank Links",
            ["Session ID", "ASPSP", "Country", "Accounts", "Status", "Authorized"],
            rows,
            "No bank links found.",
        )

    def delete_link(self, session_id: str) -> None:
        self.provider.delete_session(session_id)
        self.console.print(f"Deleted session {session_id}.")

    def create_link(
        self,
        aspsp_name: str,
        aspsp_country: str,
        callback_host: str,
        callback_port: int,
        psu_type: str = "personal",
        access_days: int = 90,
        open_browser: bool = True,
    ) -> None:
        session = self.provider.authorize_interactive(
            aspsp_name=aspsp_name,
            aspsp_country=aspsp_country.upper(),
            callback_host=callback_host,
            callback_port=callback_port,
            psu_type=psu_type,
            access_days=access_days,
            open_browser=open_browser,
        )
        self.console.print(
            f"Created session {session.session_id or 'unknown'} with "
            f"{len(session.accounts)} account(s)."
        )
