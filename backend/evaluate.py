from __future__ import annotations

import argparse
import json
from pathlib import Path

from screening.evaluation.pipeline import ABTestPipeline
from screening.evaluation.variants import default_variants, get_variant


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="A/B evaluate screening algorithm variants against a labeled benchmark."
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=None,
        help="Path to labeled benchmark JSON.",
    )
    parser.add_argument(
        "--watchlist",
        type=Path,
        default=None,
        help="Path to watchlist JSON.",
    )
    parser.add_argument(
        "--variants",
        nargs="*",
        default=None,
        help="Variant names to compare (default: all built-in variants).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write full JSON report.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON report to stdout.",
    )
    parser.add_argument(
        "--show-failures",
        action="store_true",
        help="Print misclassified cases per variant.",
    )
    return parser.parse_args()


def print_summary(report_dict: dict) -> None:
    print(f"Benchmark: {report_dict['benchmark_path']} ({report_dict['case_count']} cases)")
    print(f"Watchlist: {report_dict['watchlist_path']}")
    print()

    header = (
        f"{'Variant':<22} {'Flag F1':>8} {'Precision':>10} {'Recall':>8} "
        f"{'Block F1':>9} {'Accuracy':>10} {'Entity Hit':>11} {'ms/case':>8}"
    )
    print(header)
    print("-" * len(header))

    for variant in report_dict["variants"]:
        flag = variant["flag_metrics"]
        block = variant["block_metrics"]
        entity = variant.get("entity_hit_rate")
        entity_text = f"{entity * 100:.1f}%" if entity is not None else "n/a"
        print(
            f"{variant['variant_name']:<22} "
            f"{flag['f1_score']:>8.3f} "
            f"{flag['precision']:>10.3f} "
            f"{flag['recall']:>8.3f} "
            f"{block['f1_score']:>9.3f} "
            f"{flag['accuracy']:>10.3f} "
            f"{entity_text:>11} "
            f"{variant['avg_latency_ms']:>8.2f}"
        )

    print()
    print(f"Best Flag F1:    {report_dict['winner_by_flag_f1']}")
    print(f"Best Block F1:   {report_dict['winner_by_block_f1']}")
    if report_dict.get("winner_by_verdict_macro_f1"):
        print(f"Best Verdict F1: {report_dict['winner_by_verdict_macro_f1']}")


def print_failures(report_dict: dict) -> None:
    for variant in report_dict["variants"]:
        failures = [
            prediction
            for prediction in variant["predictions"]
            if not prediction["correct_flag"]
        ]
        if not failures:
            continue

        print(f"\nMisclassified cases — {variant['variant_name']}:")
        for failure in failures:
            print(
                f"  [{failure['case_id']}] {failure['category']}: "
                f"expected={failure['expected_label'].value if hasattr(failure['expected_label'], 'value') else failure['expected_label']} "
                f"got={failure['predicted_verdict']} "
                f"(conf={failure['confidence']:.1f}%)"
            )


def main() -> None:
    args = parse_args()
    pipeline = ABTestPipeline.from_paths(args.benchmark, args.watchlist)

    if args.variants:
        variants = [get_variant(name) for name in args.variants]
    else:
        variants = default_variants()

    report = pipeline.run_ab_test(variants)
    report_dict = report.model_dump(mode="json")

    if args.json:
        print(json.dumps(report_dict, indent=2))
    else:
        print_summary(report_dict)

    if args.show_failures:
        print_failures(report_dict)

    if args.output:
        args.output.write_text(json.dumps(report_dict, indent=2), encoding="utf-8")
        if not args.json:
            print(f"\nFull report written to {args.output}")


if __name__ == "__main__":
    main()
