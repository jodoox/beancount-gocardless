import argparse
import sys
import os
import logging

from beancount_gocardless.models import AccountInfo
from beancount_gocardless.client import GoCardlessClient


logging.basicConfig(level=os.environ.get("LOGLEVEL", logging.INFO))
logger = logging.getLogger(__name__)


def display_account(index: int, account: AccountInfo) -> None:
    """Helper function to display account information."""
    iban = account.get("iban", "no-iban")
    currency = "no-currency"  # not in AccountInfo
    name = account.get("name", "no-name")
    institution_id = account.get("institution_id", "no-institution")
    requisition_ref = account.get("requisition_reference", "no-ref")
    account_id = account.get("id", "no-id")
    logger.info(
        f"{index}: {institution_id} {name}: {iban} {currency} ({requisition_ref}/{account_id})"
    )


def parse_args():
    parser = argparse.ArgumentParser(description="GoCardless CLI Utility")
    parser.add_argument(
        "mode",
        choices=[
            "list_banks",
            "create_link",
            "list_accounts",
            "delete_link",
            "balance",
        ],
        help="Operation mode",
    )
    parser.add_argument(
        "--secret_id",
        default=os.getenv("GOCARDLESS_SECRET_ID"),
        help="API secret ID (defaults to env var GOCARDLESS_SECRET_ID)",
    )
    parser.add_argument(
        "--secret_key",
        default=os.getenv("GOCARDLESS_SECRET_KEY"),
        help="API secret key (defaults to env var GOCARDLESS_SECRET_KEY)",
    )
    parser.add_argument(
        "--country", default="GB", help="Country code for listing banks"
    )
    parser.add_argument(
        "--reference", default="beancount", help="Unique reference for bank linking"
    )
    parser.add_argument("--bank", help="Bank ID for linking")
    parser.add_argument("--account", help="Account ID for operations")
    parser.add_argument("--cache", action="store_true", help="Enable caching")
    parser.add_argument(
        "--cache_backend", default="sqlite", help="Cache backend (sqlite, memory, etc.)"
    )
    parser.add_argument(
        "--cache_expire",
        type=int,
        default=0,
        help="Cache expiration in seconds (0 = never expire)",
    )
    parser.add_argument(
        "--cache_name", default="gocardless", help="Cache name/database file"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if not args.secret_id or not args.secret_key:
        logger.error(
            "Error: Secret ID and Secret Key are required (pass as args or set env vars GOCARDLESS_SECRET_ID and GOCARDLESS_SECRET_KEY)",
        )
        sys.exit(1)

    try:
        logger.debug("Initializing GoCardlessClient")

        cache_options = (
            {
                "backend": args.cache_backend,
                "expire_after": args.cache_expire,
                "cache_name": args.cache_name,
            }
            if args.cache
            else {}
        )

        client = GoCardlessClient(args.secret_id, args.secret_key, cache_options)

        if args.mode == "list_banks":
            banks = client.list_banks(args.country)
            for bank in banks:
                logger.info(bank)
        elif args.mode == "create_link":
            if not args.bank:
                logger.error("Error: --bank is required for create_link")
                sys.exit(1)
            link = client.create_bank_link(args.reference, args.bank)
            if link:
                logger.info(f"Bank link created: {link}")
            else:
                logger.info(f"Link already exists for reference '{args.reference}'")
        elif args.mode == "list_accounts":
            accounts = client.list_accounts()
            for i, account in enumerate(accounts, 1):
                display_account(i, account)
        elif args.mode == "delete_link":
            req = client.find_requisition_by_reference(args.reference)
            if req:
                client.delete_requisition(req.id)
                logger.info(f"Deleted requisition '{args.reference}'")
            else:
                logger.error(f"No requisition found with reference '{args.reference}'")
                sys.exit(1)
        elif args.mode == "balance":
            if not args.account:
                logger.error("Error: --account is required for balance")
                sys.exit(1)
            balances = client.get_account_balances(args.account)
            for balance in balances.balances:
                logger.info(
                    f"{balance.balance_type}: {balance.balance_amount.amount} {balance.balance_amount.currency}"
                )

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
