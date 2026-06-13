"""Generate a human-readable variant comparison report.

Usage (from backend/):
    python report.py                          # prints to console + saves reports/screening_report.txt
    python report.py --output my_report.txt   # custom output path
    python report.py --no-save                # console only
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from screening.evaluation.pipeline import ABTestPipeline
from screening.evaluation.variants import default_variants
from screening.watchlist_repo import default_db_path

_W = 62  # report width


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #

def _composite_score(variant: dict) -> float:
    """60 % F2 + 40 % MCC.

    F2 weights recall over precision — missing a sanctioned entity is the
    primary compliance risk. MCC is robust when clean transactions vastly
    outnumber hits (typical in sanctions screening).
    """
    f2 = variant["flag_metrics"]["f2_score"]
    mcc = variant["flag_metrics"]["mcc"]
    return round(0.6 * f2 + 0.4 * mcc, 4)


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #

def _line(char: str = "─") -> str:
    return char * _W


def _header(title: str, char: str = "═") -> str:
    return f"\n{char * _W}\n  {title}\n{char * _W}"


def _pct(value: float, decimals: int = 1) -> str:
    return f"{value * 100:.{decimals}f}%"


def _score_bar(score: float, width: int = 20) -> str:
    filled = round(score * width)
    return "█" * filled + "░" * (width - filled)


def _risk_label(false_negative_rate: float) -> str:
    if false_negative_rate <= 0.02:
        return "LOW RISK"
    if false_negative_rate <= 0.08:
        return "MODERATE RISK"
    return "HIGH RISK !"


def _workload_label(alert_rate: float) -> str:
    if alert_rate <= 0.10:
        return "low workload"
    if alert_rate <= 0.20:
        return "moderate workload"
    return "high workload"


# --------------------------------------------------------------------------- #
# Report sections
# --------------------------------------------------------------------------- #

def _section_header(report: dict) -> list[str]:
    db_path = Path(report["watchlist_path"])
    db_label = db_path.name if db_path.exists() else str(db_path)
    bench_label = Path(report["benchmark_path"]).name
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M UTC")

    lines = [
        _line("═"),
        "  SANCTIONS SCREENING — VARIANT COMPARISON REPORT",
        _line("═"),
        f"  Generated : {generated}",
        f"  Benchmark : {bench_label}  ({report['case_count']} test cases)",
        f"  Watchlist : {db_label}",
    ]
    return lines


def _section_ranking(variants: list[dict], scores: list[float]) -> list[str]:
    lines = [_header("RANKING  (composite score = 60% F2 + 40% MCC)")]
    lines.append("")
    lines.append(f"  {'#':<4} {'Variant':<24} {'Score':>6}  {'':20}  Status")
    lines.append(f"  {_line('-')}")

    ranked = sorted(zip(scores, variants), key=lambda x: x[0], reverse=True)
    for rank, (score, v) in enumerate(ranked, start=1):
        bar = _score_bar(score)
        badge = "★ RECOMMENDED" if rank == 1 else ""
        lines.append(f"  #{rank:<3} {v['variant_name']:<24} {score:>6.3f}  {bar}  {badge}")

    lines.append("")
    lines.append("  Composite score: F2 rewards catching real hits;")
    lines.append("  MCC stays honest when clean payments dominate (99%+ of volume).")
    return lines


def _section_key_metrics(variants: list[dict], scores: list[float]) -> list[str]:
    ranked = [v for _, v in sorted(zip(scores, variants), key=lambda x: x[0], reverse=True)]

    col = 14
    names = [v["variant_name"] for v in ranked]
    header_row = f"  {'Metric':<26}" + "".join(f"{n[:col]:>{col}}" for n in names)

    lines = [_header("KEY METRICS  (ranked best → worst)")]
    lines.append("")
    lines.append(header_row)
    lines.append(f"  {_line('-')}")

    def row(label: str, values: list[str]) -> str:
        return f"  {label:<26}" + "".join(f"{val:>{col}}" for val in values)

    lines.append(row(
        "Detection Rate (Recall)",
        [_pct(v["flag_metrics"]["recall"]) for v in ranked],
    ))
    lines.append(row(
        "Miss Rate  ← risk",
        [_pct(v["flag_metrics"]["false_negative_rate"]) for v in ranked],
    ))
    lines.append(row(
        "False Alarm Rate",
        [_pct(v["flag_metrics"]["false_positive_rate"]) for v in ranked],
    ))
    lines.append(row(
        "Alert Precision",
        [_pct(v["flag_metrics"]["precision"]) for v in ranked],
    ))
    lines.append(f"  {_line('-')}")
    lines.append(row(
        "F2 Score",
        [f"{v['flag_metrics']['f2_score']:.3f}" for v in ranked],
    ))
    lines.append(row(
        "MCC",
        [f"{v['flag_metrics']['mcc']:.3f}" for v in ranked],
    ))
    lines.append(row(
        "F1 Score",
        [f"{v['flag_metrics']['f1_score']:.3f}" for v in ranked],
    ))
    lines.append(f"  {_line('-')}")
    lines.append(row(
        "Alert Rate",
        [_pct(v["flag_metrics"]["alert_rate"]) for v in ranked],
    ))
    lines.append(row(
        "Auto-Block Rate",
        [_pct(v["block_metrics"]["alert_rate"]) for v in ranked],
    ))
    entity_vals = []
    for v in ranked:
        hit = v.get("entity_hit_rate")
        entity_vals.append(_pct(hit) if hit is not None else "  n/a")
    lines.append(row("Entity Hit Rate", entity_vals))
    lines.append(row(
        "Speed (ms / txn)",
        [f"{v['avg_latency_ms']:.1f} ms" for v in ranked],
    ))

    return lines


def _section_tradeoffs(variants: list[dict], scores: list[float]) -> list[str]:
    ranked = [v for _, v in sorted(zip(scores, variants), key=lambda x: x[0], reverse=True)]

    lines = [_header("TRADE-OFF ANALYSIS")]
    lines.append("")

    for rank, v in enumerate(ranked, start=1):
        fm = v["flag_metrics"]
        fnr = fm["false_negative_rate"]
        fpr = fm["false_positive_rate"]
        alert_rate = fm["alert_rate"]
        score = scores[variants.index(v)]

        risk = _risk_label(fnr)
        workload = _workload_label(alert_rate)
        badge = "  ★ top pick" if rank == 1 else ""

        lines.append(f"  #{rank}  {v['variant_name']}{badge}")
        lines.append(f"      {v['variant_description']}")
        lines.append(f"      Compliance risk : {risk}  (misses {_pct(fnr)} of real hits)")
        lines.append(f"      Analyst workload: {workload}  ({_pct(alert_rate)} of payments flagged)")
        lines.append(f"      False alarms    : {_pct(fpr)} of clean payments wrongly stopped")
        lines.append(f"      Composite score : {score:.3f}")
        lines.append("")

    return lines


def _section_confusion(variants: list[dict], scores: list[float]) -> list[str]:
    ranked = [v for _, v in sorted(zip(scores, variants), key=lambda x: x[0], reverse=True)]

    lines = [_header("CONFUSION MATRIX PER VARIANT")]
    lines.append("")
    lines.append("  (flag metrics: MATCH + REVIEW count as 'flagged')")
    lines.append("")

    for v in ranked:
        fm = v["flag_metrics"]
        tp, tn = fm["true_positives"], fm["true_negatives"]
        fp, fn = fm["false_positives"], fm["false_negatives"]
        lines.append(f"  {v['variant_name']}")
        lines.append(f"    Correct Alerts  (TP) {tp:>4}  │  Missed Hits    (FN) {fn:>4}  ← compliance risk")
        lines.append(f"    False Alarms    (FP) {fp:>4}  │  Clean Passes   (TN) {tn:>4}")
        lines.append("")

    return lines


def _section_recommendation(variants: list[dict], scores: list[float]) -> list[str]:
    ranked = sorted(zip(scores, variants), key=lambda x: x[0], reverse=True)
    best_score, best = ranked[0]
    fm = best["flag_metrics"]
    bm = best["block_metrics"]

    lines = [_header("RECOMMENDATION", "═")]
    lines.append("")
    lines.append(f"  Use  →  {best['variant_name']}")
    lines.append(f"          {best['variant_description']}")
    lines.append("")
    lines.append(f"  It catches {_pct(fm['recall'])} of sanctioned entities")
    lines.append(f"  with a miss rate of only {_pct(fm['false_negative_rate'])} (compliance exposure).")
    lines.append(f"  {_pct(fm['false_positive_rate'])} of clean payments are wrongly stopped,")
    lines.append(f"  keeping analyst queue volume at {_pct(fm['alert_rate'])}.")
    if bm["precision"] > 0:
        lines.append(f"  Auto-blocked payments have {_pct(bm['precision'])} precision —")
        lines.append(f"  meaning {_pct(bm['precision'])} of hard blocks are confirmed hits.")
    lines.append("")
    config = best.get("config", {})
    if config:
        lines.append("  Thresholds:")
        for key, val in config.items():
            lines.append(f"    {key:<24} {val}")
    lines.append("")
    lines.append(_line("═"))
    return lines


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def build_report(report_dict: dict) -> str:
    variants = report_dict["variants"]
    scores = [_composite_score(v) for v in variants]

    sections = [
        _section_header(report_dict),
        _section_ranking(variants, scores),
        _section_key_metrics(variants, scores),
        _section_tradeoffs(variants, scores),
        _section_confusion(variants, scores),
        _section_recommendation(variants, scores),
    ]

    lines: list[str] = []
    for section in sections:
        lines.extend(section)
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a screening variant comparison report.")
    parser.add_argument("--benchmark", type=Path, default=None, help="Path to benchmark JSON.")
    parser.add_argument("--db", type=Path, default=None, help="Path to AML SQLite database.")
    parser.add_argument("--output", type=Path, default=None, help="File path for the saved report.")
    parser.add_argument("--no-save", action="store_true", help="Print only, do not save to file.")
    args = parser.parse_args()

    print("Running evaluation…", file=sys.stderr)
    pipeline = ABTestPipeline.from_db(args.benchmark, args.db)
    report_dict = pipeline.run_ab_test(default_variants()).model_dump(mode="json")

    report_text = build_report(report_dict)
    print(report_text)

    if not args.no_save:
        out_path = args.output or Path("reports") / "screening_report.txt"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report_text, encoding="utf-8")
        print(f"Report saved → {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
