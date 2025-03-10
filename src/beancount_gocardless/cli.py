import argparse
import sys
import os
from .client import NordigenClient


def parse_args():
    """
    Parses command-line arguments.

    Returns:
        argparse.Namespace: An object containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Nordigen CLI Utility")
    parser.add_argument(
        "mode",
        choices=["list_banks", "create_link", "list_accounts", "delete_link"],
        help="Operation mode",
    )
    parser.add_argument(
        "--secret_id",
        default=os.getenv("NORDIGEN_SECRET_ID"),
        help="API secret ID (defaults to env var NORDIGEN_SECRET_ID)",
    )
    parser.add_argument(
        "--secret_key",
        default=os.getenv("NORDIGEN_SECRET_KEY"),
        help="API secret key (defaults to env var NORDIGEN_SECRET_KEY)",
    )
    parser.add_argument(
        "--country", default="GB", help="Country code for listing banks"
    )
    parser.add_argument(
        "--reference", default="beancount", help="Unique reference for bank linking"
    )
    parser.add_argument("--bank", help="Bank ID for linking")
    return parser.parse_args()


def main():
    """
    The main entry point for the CLI.

    Executes the specified operation based on the parsed command-line arguments.
    """
    args = parse_args()

    if not args.secret_id or not args.secret_key:
        print(
            "Error: Secret ID and Secret Key are required (pass as args or set env vars NORDIGEN_SECRET_ID and NORDIGEN_SECRET_KEY)",
            file=sys.stderr,
        )
        sys.exit(1)

    client = NordigenClient(
        args.secret_id,
        args.secret_key,
        {},
    )

    if args.mode == "list_banks":
        banks = client.list_banks(args.country)
        for b in banks:
            print(b["name"] + ": " + b["id"])
    elif args.mode == "create_link":
        if not args.bank:
            print("--bank is required for create_link", file=sys.stderr)
            sys.exit(1)
        print(client.create_link(args.reference, args.bank))
    elif args.mode == "list_accounts":
        accounts = client.list_accounts()
        for a in accounts:
            print(
                f"{a['institution_id']} {a['name']}: {a['iban']} {a['currency']} ({a['reference']}/{a['id']})"
            )

    elif args.mode == "delete_link":
        print(client.delete_link(args.reference))


if __name__ == "__main__":
    main()
