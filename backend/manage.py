"""Unified CLI for the TeslaFinTech sanctions screening backend.

Usage (from backend/):
    python manage.py fetch                    # ingest OFAC SDN list into DB
    python manage.py screen --name "John Doe" # screen a single counterparty
    python manage.py screen --transactions txns.json
    python manage.py evaluate                 # A/B evaluate all variants
    python manage.py evaluate --variants fuzzy exact --show-failures
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# --------------------------------------------------------------------------- #
# fetch
# --------------------------------------------------------------------------- #

def cmd_fetch(args: argparse.Namespace) -> None:
    from app.logging_config import configure_logging
    from app.ingestion.ofac_sdn import run_ingestion

    configure_logging()
    result = run_ingestion()
    print(f"Ingestion complete: {result}")


# --------------------------------------------------------------------------- #
# screen
# --------------------------------------------------------------------------- #

def cmd_screen(args: argparse.Namespace) -> None:
    from screening.engine import ScreeningEngine
    from screening.models import Transaction
    from screening.watchlist_repo import default_db_path, load_watchlist_from_db

    db_path = args.db or default_db_path()
    watchlist = load_watchlist_from_db(db_path)
    engine = ScreeningEngine(watchlist)

    if args.transactions:
        payload = json.loads(Path(args.transactions).read_text(encoding="utf-8"))
        transactions = [Transaction.model_validate(item) for item in payload]
    elif args.name:
        transactions = [
            Transaction(
                transaction_id=args.transaction_id,
                counterparty_name=args.name,
                counterparty_country=args.country,
            )
        ]
    else:
        sys.exit("Provide --transactions FILE or --name NAME.")

    for txn in transactions:
        result = engine.screen(txn)
        d = result.model_dump()
        if args.json:
            print(json.dumps(d, indent=2, default=str))
        else:
            print(f"\nTransaction : {d['transaction_id']}")
            print(f"Counterparty: {d['counterparty_name']}")
            print(f"Verdict     : {d['verdict']}")
            print(f"Confidence  : {d['confidence']:.1f}%")
            print(f"Explanation : {d['explanation']}")
            for match in (d.get("matched_entities") or [])[:3]:
                e = match["entity"]
                print(f"  - {e['full_name']} ({e['list_source']}) @ {match['confidence']:.1f}%")


# --------------------------------------------------------------------------- #
# evaluate
# --------------------------------------------------------------------------- #

def cmd_evaluate(args: argparse.Namespace) -> None:
    from screening.evaluation.pipeline import ABTestPipeline
    from screening.evaluation.variants import default_variants, get_variant

    pipeline = ABTestPipeline.from_db(
        Path(args.benchmark) if args.benchmark else None,
        Path(args.db) if args.db else None,
    )

    variants = [get_variant(n) for n in args.variants] if args.variants else default_variants()
    report = pipeline.run_ab_test(variants)
    report_dict = report.model_dump(mode="json")

    if args.json:
        print(json.dumps(report_dict, indent=2))
    else:
        _print_evaluate_summary(report_dict)

    if args.show_failures:
        _print_evaluate_failures(report_dict)

    if args.output:
        Path(args.output).write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
        if not args.json:
            print(f"\nFull report written to {args.output}")


def _print_evaluate_summary(report: dict) -> None:
    print(f"Benchmark : {report['benchmark_path']} ({report['case_count']} cases)")
    print(f"Watchlist : {report['watchlist_path']}")
    print()
    header = (
        f"{'Variant':<22} {'Flag F1':>8} {'Precision':>10} {'Recall':>8} "
        f"{'Block F1':>9} {'Accuracy':>10} {'Entity Hit':>11} {'ms/case':>8}"
    )
    print(header)
    print("-" * len(header))
    for v in report["variants"]:
        flag = v["flag_metrics"]
        block = v["block_metrics"]
        entity = v.get("entity_hit_rate")
        entity_text = f"{entity * 100:.1f}%" if entity is not None else "n/a"
        print(
            f"{v['variant_name']:<22} "
            f"{flag['f1_score']:>8.3f} "
            f"{flag['precision']:>10.3f} "
            f"{flag['recall']:>8.3f} "
            f"{block['f1_score']:>9.3f} "
            f"{flag['accuracy']:>10.3f} "
            f"{entity_text:>11} "
            f"{v['avg_latency_ms']:>8.2f}"
        )
    print()
    print(f"Best Flag F1  : {report['winner_by_flag_f1']}")
    print(f"Best Block F1 : {report['winner_by_block_f1']}")
    if report.get("winner_by_verdict_macro_f1"):
        print(f"Best Verdict F1: {report['winner_by_verdict_macro_f1']}")


def _print_evaluate_failures(report: dict) -> None:
    for v in report["variants"]:
        failures = [p for p in v["predictions"] if not p["correct_flag"]]
        if not failures:
            continue
        print(f"\nMisclassified — {v['variant_name']}:")
        for f in failures:
            label = f["expected_label"]
            if hasattr(label, "value"):
                label = label.value
            print(
                f"  [{f['case_id']}] {f['category']}: "
                f"expected={label} got={f['predicted_verdict']} "
                f"(conf={f['confidence']:.1f}%)"
            )


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="TeslaFinTech sanctions screening management CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # fetch
    sub.add_parser("fetch", help="Fetch and ingest the OFAC SDN list into the database.")

    # screen
    s = sub.add_parser("screen", help="Screen one or more transactions against the watchlist.")
    s.add_argument("--db", type=Path, default=None, help="Path to AML SQLite database.")
    s.add_argument("--transactions", metavar="FILE", help="JSON file with a list of transactions.")
    s.add_argument("--name", help="Counterparty name for a single ad-hoc screen.")
    s.add_argument("--country", help="Counterparty ISO country code.")
    s.add_argument("--transaction-id", default="cli-txn", help="Transaction ID for ad-hoc screening.")
    s.add_argument("--json", action="store_true", help="Output raw JSON.")

    # evaluate
    e = sub.add_parser("evaluate", help="A/B evaluate screening variants against a benchmark.")
    e.add_argument("--benchmark", metavar="FILE", help="Path to labeled benchmark JSON.")
    e.add_argument("--db", type=Path, default=None, help="Path to AML SQLite database.")
    e.add_argument("--variants", nargs="*", metavar="NAME", help="Variant names to compare.")
    e.add_argument("--output", metavar="FILE", help="Write full JSON report to this path.")
    e.add_argument("--json", action="store_true", help="Print full JSON report to stdout.")
    e.add_argument("--show-failures", action="store_true", help="Print misclassified cases.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "fetch": cmd_fetch,
        "screen": cmd_screen,
        "evaluate": cmd_evaluate,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
