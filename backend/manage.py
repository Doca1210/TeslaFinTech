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

    configure_logging()

    if args.source == "ofac-sdn":
        from app.ingestion.ofac_sdn import run_ingestion

        result = run_ingestion()
    elif args.source == "opensanctions-peps":
        from app.ingestion.opensanctions import run_ingestion

        result = run_ingestion(dataset="peps", limit=args.limit if args.limit > 0 else None)
    else:
        from app.ingestion.opensanctions import run_ingestion

        result = run_ingestion(dataset="eu_fsf", limit=None)

    print(f"Ingestion complete: {result}")


# --------------------------------------------------------------------------- #
# export
# --------------------------------------------------------------------------- #

def cmd_export(args: argparse.Namespace) -> None:
    from app.logging_config import configure_logging
    from app.export.vectorize_export import export_entities

    configure_logging()
    result = export_entities(output_path=args.output)
    print(f"Export complete: {result}")


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
    _W = 56
    _LINE = "─" * _W

    print()
    print(f"  Benchmark : {report['benchmark_path']}")
    print(f"  Watchlist : {report['watchlist_path']}")
    print(f"  Cases     : {report['case_count']}")

    for v in report["variants"]:
        flag = v["flag_metrics"]
        block = v["block_metrics"]
        entity_hit = v.get("entity_hit_rate")
        entity_cases = v.get("entity_cases", 0)

        print()
        print(_LINE)
        print(f"  {v['variant_name']}  ·  {v['variant_description']}")
        print(_LINE)

        # ── Detection ────────────────────────────────────────────
        print()
        print("  DETECTION  (did we catch every real hit?)")
        _row("Detection Rate",   flag["recall"],            pct=True,
             note="of real sanctioned entities correctly flagged")
        _row("Miss Rate",        flag["false_negative_rate"], pct=True,
             note="hits that slipped through  ← compliance risk", warn=flag["false_negative_rate"] > 0.05)
        _row("False Alarm Rate", flag["false_positive_rate"], pct=True,
             note="clean payments wrongly flagged  ← analyst workload")
        _row("Alert Precision",  flag["precision"],          pct=True,
             note="of raised alerts that are genuine hits")

        # ── Quality scores ────────────────────────────────────────
        print()
        print("  QUALITY SCORES")
        _row("F1 Score",  flag["f1_score"],  note="balanced precision / recall  (0–1, higher is better)")
        _row("F2 Score",  flag["f2_score"],  note="recall-weighted  (penalises misses 2× more than false alarms)")
        _row("MCC",       flag["mcc"],       note="overall quality on imbalanced data  (0–1, higher is better)")
        _row("Accuracy",  flag["accuracy"],  pct=True, note="correct decisions across all cases")

        # ── Auto-block quality ────────────────────────────────────
        print()
        print("  AUTO-BLOCK QUALITY  (MATCH verdict only)")
        _row("Block Precision", block["precision"], pct=True,
             note="of hard-blocked payments that are confirmed hits")
        _row("Block Recall",    block["recall"],    pct=True,
             note="of highest-confidence hits that were auto-blocked")
        _row("Block F1",        block["f1_score"],  note="balanced score for auto-block decisions")

        # ── Operational ──────────────────────────────────────────
        print()
        print("  OPERATIONAL")
        _row("Alert Rate",      flag["alert_rate"],  pct=True,
             note="transactions routed to the review queue")
        _row("Auto-Block Rate", block["alert_rate"], pct=True,
             note="transactions hard-blocked without analyst review")
        if entity_hit is not None:
            _row("Entity Hit Rate", entity_hit, pct=True,
                 note=f"correct entity identified ({entity_cases} cases with known target)")
        _row("Speed", v["avg_latency_ms"], unit=" ms", note="average screening latency per transaction")

        # ── Confusion matrix ─────────────────────────────────────
        tp = flag["true_positives"]
        tn = flag["true_negatives"]
        fp = flag["false_positives"]
        fn = flag["false_negatives"]
        print()
        print("  CONFUSION MATRIX")
        print(f"    {'Correct Alerts (TP)':<24} {tp:>5}    {'Missed Hits (FN)':<24} {fn:>5}  ← compliance risk")
        print(f"    {'False Alarms (FP)':<24} {fp:>5}    {'Clean Passes (TN)':<24} {tn:>5}")

    # ── Winner summary ───────────────────────────────────────────
    print()
    print(_LINE)
    print("  RECOMMENDED VARIANT")
    print(f"    Best overall (F2)   : {report['winner_by_flag_f1']}")
    print(f"    Best auto-block     : {report['winner_by_block_f1']}")
    if report.get("winner_by_verdict_macro_f1"):
        print(f"    Best 3-way verdict  : {report['winner_by_verdict_macro_f1']}")
    print(_LINE)
    print()


def _row(label: str, value: float, *, pct: bool = False, unit: str = "", note: str = "", warn: bool = False) -> None:
    if pct:
        value_str = f"{value * 100:>6.1f}%"
    elif unit:
        value_str = f"{value:>6.1f}{unit}"
    else:
        value_str = f"{value:>7.4f}"
    flag_str = "  !" if warn else ""
    note_str = f"  {note}" if note else ""
    print(f"    {label:<22} {value_str}{flag_str}{note_str}")


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
    f = sub.add_parser("fetch", help="Fetch and ingest a source list into the database.")
    f.add_argument(
        "--source",
        choices=["ofac-sdn", "opensanctions-peps", "opensanctions-eu"],
        default="ofac-sdn",
        help="Which source to ingest (default: ofac-sdn).",
    )
    f.add_argument(
        "--limit",
        type=int,
        default=20_000,
        help="Max rows for opensanctions-peps (0 = full feed, 1M+ rows). Ignored otherwise.",
    )

    # export
    x = sub.add_parser("export", help="Export entities to JSONL for vectorization.")
    x.add_argument("--output", type=Path, default=None, help="Output JSONL path.")

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
        "export": cmd_export,
        "screen": cmd_screen,
        "evaluate": cmd_evaluate,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
