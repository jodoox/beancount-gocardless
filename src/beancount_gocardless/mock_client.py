"""Mock GoCardless client for CLI testing.

Returns synthetic demo data without making real API calls.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from .client import GoCardlessClient
from .models import (
    Institution,
    Requisition,
    Account,
    AccountBalance,
    AccountInfo,
    BalanceSchema,
    BalanceAmountSchema,
)

logger = logging.getLogger(__name__)

__all__ = ["MockGoCardlessClient"]


class MockGoCardlessClient(GoCardlessClient):
    """Mock client that returns synthetic demo data instead of making API calls."""

    def __init__(
        self,
        secret_id: str,
        secret_key: str,
        cache_options: Optional[Dict[str, Any]] = None,
    ):
        """Initialize mock client."""
        logger.info("Initializing MockGoCardlessClient")
        self._token = "mock-token"
        self.secret_id = secret_id
        self.secret_key = secret_key

    def list_banks(self, country: Optional[str] = None) -> List[str]:
        """Get bank names."""
        institutions = self.get_institutions(country)
        return [inst.name for inst in institutions]

    def get_institutions(self, country: Optional[str] = None) -> List[Institution]:
        """Get demo institutions."""
        logger.debug(f"MockClient: Getting institutions for country {country}")
        institutions = [
            Institution(
                id="SOGEFRPP",
                name="Société Générale",
                bic="SOGEFRPP",
                transaction_total_days="730",
                countries=["FR"],
                logo=None,
            ),
            Institution(
                id="BNPAFRPP",
                name="BNP Paribas",
                bic="BNPAFRPP",
                transaction_total_days="730",
                countries=["FR"],
                logo=None,
            ),
            Institution(
                id="DEUTSCHE",
                name="Deutsche Bank",
                bic="DEUTSCH",
                transaction_total_days="730",
                countries=["DE"],
                logo=None,
            ),
        ]

        if country:
            institutions = [i for i in institutions if country in i.countries]

        return institutions

    def get_institution(self, institution_id: str) -> Institution:
        """Get specific institution."""
        logger.debug(f"MockClient: Getting institution {institution_id}")
        institutions = self.get_institutions()
        for inst in institutions:
            if inst.id == institution_id:
                return inst
        raise ValueError(f"Institution {institution_id} not found")

    def get_requisitions(self) -> List[Requisition]:
        """Get demo requisitions."""
        logger.debug("MockClient: Getting requisitions")
        accounts = self.get_accounts()
        if not accounts:
            return []

        requisitions = []
        references = [
            "main-checking",
            "savings-account",
            "joint-account",
            "business-account",
        ]

        for i in range(0, len(accounts), 2):
            ref_idx = (i // 2) % len(references)
            requisitions.append(
                Requisition(
                    id=f"req_{i}",
                    created=datetime.now().isoformat(),
                    redirect="http://localhost",
                    reference=references[ref_idx],
                    status="LINKED",
                    institution_id="SOGEFRPP" if i % 2 == 0 else "BNPAFRPP",
                    accounts=[acc.id for acc in accounts[i : i + 2]],
                    access_valid_for_days=90,
                )
            )
        return requisitions

    def get_account(self, account_id: str) -> Account:
        """Get demo account."""
        logger.debug(f"MockClient: Getting account {account_id}")
        accounts = self.get_accounts()
        for acc in accounts:
            if acc.id == account_id:
                return acc
        raise ValueError(f"Account {account_id} not found")

    def get_accounts(self) -> List[Account]:
        """Get demo accounts."""
        return [
            Account(
                id="acc_001",
                created=datetime.now().isoformat(),
                status="READY",
                institution_id="SOGEFRPP",
                name="Main Checking",
                iban="FR1420041010050500013M02606",
            ),
            Account(
                id="acc_002",
                created=datetime.now().isoformat(),
                status="READY",
                institution_id="BNPAFRPP",
                name="Savings Account",
                iban="FR7613807000013000060004391",
            ),
        ]

    def get_account_balances(self, account_id: str) -> AccountBalance:
        """Get demo account balances."""
        logger.debug(f"MockClient: Getting balances for account {account_id}")
        return AccountBalance(
            balances=[
                BalanceSchema(
                    balance_amount=BalanceAmountSchema(
                        amount="2547.83", currency="EUR"
                    ),
                    balance_type="interimAvailable",
                ),
                BalanceSchema(
                    balance_amount=BalanceAmountSchema(
                        amount="2490.00", currency="EUR"
                    ),
                    balance_type="closingBooked",
                ),
            ]
        )

    def list_accounts(self) -> List[AccountInfo]:
        """Get all accounts with expiry info."""
        logger.debug("MockClient: Getting all accounts")
        accounts = self.get_accounts()
        requisitions = self.get_requisitions()
        result = []

        for i, account in enumerate(accounts):
            account_dict = account.model_dump()
            req = requisitions[i // 2] if requisitions else None
            req_status = req.status if req else "LINKED"
            req_created = req.created if req else datetime.now().isoformat()
            req_id = req.id if req else f"mock-req-{i // 2}"
            req_ref = req.reference if req else f"mock-ref-{i // 2}"
            access_days = (
                req.access_valid_for_days if req and req.access_valid_for_days else 90
            )

            created_date = datetime.fromisoformat(req_created.replace("Z", "+00:00"))
            expiry_date = created_date + timedelta(days=access_days)
            is_expired = req_status == "EX"

            account_dict.update(
                {
                    "requisition_id": req_id,
                    "requisition_reference": req_ref,
                    "institution_id": account.institution_id or "mock-inst",
                    "requisition_status": req_status,
                    "access_valid_until": expiry_date.isoformat(),
                    "is_expired": is_expired,
                }
            )
            result.append(account_dict)
        return result

    def create_requisition(self, *args, **kwargs):
        raise NotImplementedError("MockClient does not support creating requisitions")

    def create_bank_link(self, *args, **kwargs):
        raise NotImplementedError("MockClient does not support creating bank links")

    def delete_requisition(self, *args, **kwargs):
        raise NotImplementedError("MockClient does not support deleting requisitions")

    def find_requisition_by_reference(self, reference: str) -> Optional[Requisition]:
        """Find requisition by reference."""
        requisitions = self.get_requisitions()
        return next((req for req in requisitions if req.reference == reference), None)

    def get_all_accounts(self) -> List[AccountInfo]:
        """Alias for list_accounts."""
        return self.list_accounts()
