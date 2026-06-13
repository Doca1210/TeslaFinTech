from __future__ import annotations

import argparse
import json
from pathlib import Path

from screening.engine import ScreeningEngine
from screening.models import Transaction
from screening.watchlist_repo import default_db_path, load_watchlist_from_db


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Screen transactions against OFAC / sanctions watchlists."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=default_db_path(),
        help="Path to AML SQLite database (default: backend/aml.db).",
    )
    parser.add_argument(
        "--transactions",
        type=Path,
        help="Path to transactions JSON file. If omitted, use --name.",
    )
    parser.add_argument("--name", help="Counterparty name for a single ad-hoc screen.")
    parser.add_argument("--country", help="Counterparty ISO country code.")
    parser.add_argument(
        "--transaction-id",
        default="cli-txn",
        help="Transaction ID for ad-hoc screening.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON output instead of a human-readable summary.",
    )
    return parser.parse_args()


def load_transactions(args: argparse.Namespace) -> list[Transaction]:
    if args.transactions:
        payload = json.loads(args.transactions.read_text(encoding="utf-8"))
        return [Transaction.model_validate(item) for item in payload]

    if not args.name:
        raise SystemExit("Provide --transactions or --name.")

    return [
        Transaction(
            transaction_id=args.transaction_id,
            counterparty_name=args.name,
            counterparty_country=args.country,
        )
    ]


def print_result(result_dict: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result_dict, indent=2, default=str))
        return

    print(f"\nTransaction: {result_dict['transaction_id']}")
    print(f"Counterparty: {result_dict['counterparty_name']}")
    print(f"Verdict: {result_dict['verdict']}")
    print(f"Confidence: {result_dict['confidence']:.1f}%")
    print(f"Explanation: {result_dict['explanation']}")

    matches = result_dict.get("matched_entities") or []
    if matches:
        print("Top matches:")
        for match in matches[:3]:
            entity = match["entity"]
            print(
                f"  - {entity['full_name']} ({entity['list_source']}) "
                f"@ {match['confidence']:.1f}%"
            )


def main() -> None:
    args = parse_args()
    watchlist = load_watchlist_from_db(args.db)
    engine = ScreeningEngine(watchlist)
    transactions = load_transactions(args)

    for transaction in transactions:
        result = engine.screen(transaction)
        print_result(result.model_dump(), as_json=args.json)


if __name__ == "__main__":
    main()
