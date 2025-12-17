import argparse
import sys
import os
import logging
from beancount_gocardless.client import GoCardlessClient
from beancount_gocardless.models import AccountInfo


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

        # Build cache options
        cache_options = None
        if args.cache:
            cache_options = {
                "cache_name": args.cache_name,
                "backend": args.cache_backend,
                "expire_after": args.cache_expire,
                "old_data_on_error": True,
                "match_headers": False,
                "cache_control": False,
            }

        # client = GoCardlessClient(
        #     args.secret_id, args.secret_key, cache_options=cache_options
        # )

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
