"""Generate a human-readable v2 engine performance report.

Usage (from backend/):
    python report.py                          # prints to console + saves .txt and .html
    python report.py --output my_report.txt   # custom output path
    python report.py --no-save                # console only
    python report.py --html-only              # skip console, save HTML only
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from evaluation.pipeline import ABTestPipeline
from evaluation.variants import default_variants

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
        "  SANCTIONS SCREENING — v2 PERFORMANCE REPORT",
        _line("═"),
        f"  Generated : {generated}",
        f"  Benchmark : {bench_label}  ({report['case_count']} test cases)",
        f"  Watchlist : {db_label}",
    ]
    return lines


def _section_engine(v: dict, score: float) -> list[str]:
    fm = v["flag_metrics"]
    bar = _score_bar(score)
    lines = [_header("SCREENING ENGINE: v2_cascade")]
    lines.append(f"  {v['variant_description']}")
    lines.append("")
    lines.append(f"  Composite score : {score:.3f}  {bar}  (60% F2 + 40% MCC)")
    lines.append(f"  Risk profile    : {_risk_label(fm['false_negative_rate'])}")
    lines.append(f"  Analyst load    : {_workload_label(fm['alert_rate'])}  ({_pct(fm['alert_rate'])} of payments flagged)")
    return lines


def _section_metrics(v: dict) -> list[str]:
    fm = v["flag_metrics"]
    bm = v["block_metrics"]
    entity_hit = v.get("entity_hit_rate")
    entity_cases = v.get("entity_cases", 0)

    col_l = 26

    def row(label: str, val: str, note: str = "") -> str:
        note_part = f"  {note}" if note else ""
        return f"  {label:<{col_l}} {val:>10}{note_part}"

    lines = [_header("METRICS")]
    lines.append("")
    lines.append("  DETECTION")
    lines.append(row("Detection Rate (Recall)", _pct(fm["recall"]), "of sanctioned entities correctly flagged"))
    lines.append(row("Miss Rate  ← risk",       _pct(fm["false_negative_rate"]), "hits that slipped through"))
    lines.append(row("False Alarm Rate",         _pct(fm["false_positive_rate"]), "clean payments wrongly flagged"))
    lines.append(row("Alert Precision",          _pct(fm["precision"]), "of raised alerts that are genuine hits"))
    lines.append("")
    lines.append("  QUALITY SCORES")
    lines.append(row("F2 Score", f"{fm['f2_score']:.3f}", "recall-weighted  (standard in AML)"))
    lines.append(row("MCC",      f"{fm['mcc']:.3f}",      "robust on imbalanced data"))
    lines.append(row("F1 Score", f"{fm['f1_score']:.3f}", "balanced precision / recall"))
    lines.append("")
    lines.append("  AUTO-BLOCK  (MATCH verdict only)")
    lines.append(row("Block Precision", _pct(bm["precision"]), "of hard-blocked payments that are confirmed hits"))
    lines.append(row("Block Recall",    _pct(bm["recall"]),    "of highest-confidence hits auto-blocked"))
    lines.append(row("Block F1",        f"{bm['f1_score']:.3f}"))
    lines.append("")
    lines.append("  OPERATIONAL")
    lines.append(row("Alert Rate",      _pct(fm["alert_rate"]),  "transactions routed to review queue"))
    lines.append(row("Auto-Block Rate", _pct(bm["alert_rate"]), "transactions hard-blocked without review"))
    if entity_hit is not None:
        lines.append(row("Entity Hit Rate", _pct(entity_hit), f"correct entity identified ({entity_cases} cases)"))
    lines.append(row("Speed", f"{v['avg_latency_ms']:.1f} ms", "average latency per transaction"))
    return lines


def _section_confusion(v: dict) -> list[str]:
    fm = v["flag_metrics"]
    tp, tn = fm["true_positives"], fm["true_negatives"]
    fp, fn = fm["false_positives"], fm["false_negatives"]

    lines = [_header("CONFUSION MATRIX")]
    lines.append("")
    lines.append("  (MATCH + REVIEW both count as flagged)")
    lines.append("")
    lines.append(f"    {'Correct Alerts (TP)':<24} {tp:>5}    {'Missed Hits (FN)':<24} {fn:>5}  ← compliance risk")
    lines.append(f"    {'False Alarms (FP)':<24} {fp:>5}    {'Clean Passes (TN)':<24} {tn:>5}")
    lines.append("")
    return lines


def _section_summary(v: dict, score: float) -> list[str]:
    fm = v["flag_metrics"]
    bm = v["block_metrics"]

    lines = [_header("SUMMARY", "═")]
    lines.append("")
    lines.append(f"  Engine  →  v2_cascade")
    lines.append(f"             {v['variant_description']}")
    lines.append("")
    lines.append(f"  Catches {_pct(fm['recall'])} of sanctioned entities")
    lines.append(f"  with a miss rate of only {_pct(fm['false_negative_rate'])} (compliance exposure).")
    lines.append(f"  {_pct(fm['false_positive_rate'])} of clean payments are wrongly stopped,")
    lines.append(f"  keeping analyst queue volume at {_pct(fm['alert_rate'])}.")
    if bm["precision"] > 0:
        lines.append(f"  Auto-blocked payments have {_pct(bm['precision'])} precision.")
    lines.append("")
    config = v.get("config", {})
    if config:
        lines.append("  Configuration:")
        for key, val in config.items():
            lines.append(f"    {key:<32} {val}")
    lines.append("")
    lines.append(_line("═"))
    return lines


# --------------------------------------------------------------------------- #
# Main build
# --------------------------------------------------------------------------- #

def build_report(report_dict: dict) -> str:
    v = report_dict["variants"][0]
    score = _composite_score(v)

    sections = [
        _section_header(report_dict),
        _section_engine(v, score),
        _section_metrics(v),
        _section_confusion(v),
        _section_summary(v, score),
    ]

    lines: list[str] = []
    for section in sections:
        lines.extend(section)
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# HTML report
# --------------------------------------------------------------------------- #

_TIPS: dict[str, str] = {
    "Detection Rate": "Of all real sanctioned entities in the test set, how many were correctly flagged? Higher is better — missing a hit is a compliance violation. Target: > 95%.",
    "Miss Rate": "Of all real sanctioned entities, how many slipped through undetected? This is your direct regulatory exposure. Target: < 5%.",
    "False Alarm Rate": "Of all clean payments, what fraction were wrongly stopped? This drives analyst workload and payment delays. Target: < 15%.",
    "Alert Precision": "Of every alert raised, how many turned out to be genuine hits? Low precision means analysts waste time chasing false leads.",
    "F2 Score": "Like F1 but recall counts twice as much as precision. Standard in AML/sanctions where missing a hit (false negative) is far more costly than a false alarm. Range: 0–1.",
    "MCC": "Matthews Correlation Coefficient — a single quality score that stays honest even when 99%+ of transactions are clean. More reliable than accuracy or F1 on imbalanced data. Range: 0–1.",
    "F1 Score": "Harmonic mean of precision and recall — balanced quality measure. Penalises both false alarms and missed hits equally. Range: 0–1.",
    "Accuracy": "Percentage of all decisions that were correct. Can be misleading on imbalanced data — a model that flags nothing would score 99% accuracy if real hits are rare.",
    "Alert Rate": "Fraction of all transactions routed to the analyst review queue (MATCH + REVIEW verdicts). High alert rates burn analyst capacity.",
    "Auto-Block Rate": "Fraction of transactions hard-blocked without analyst review (MATCH verdict only). These blocks should be high-precision to avoid stopping legitimate payments.",
    "Entity Hit Rate": "When a real sanctioned entity is caught, how often is the correct entity identified as the top match? Measures identification quality beyond just flagging.",
    "Speed": "Average end-to-end time to screen one transaction. Sub-10 ms is production-grade for real-time payment rails.",
    "Composite Score": "Score = 60% F2 + 40% MCC. Weights recall-heavy performance and robustness on imbalanced data.",
    "Correct Alerts (TP)": "True Positives — real sanctioned entities that were correctly flagged. These are the alerts you want.",
    "Missed Hits (FN)": "False Negatives — real sanctioned entities that passed through undetected. Each one is a direct compliance and regulatory risk.",
    "False Alarms (FP)": "False Positives — clean payments wrongly stopped. Each one wastes analyst time and creates payment friction for legitimate customers.",
    "Clean Passes (TN)": "True Negatives — clean payments correctly released without any alert. The majority of transactions should land here.",
    "Block Precision": "Of transactions hard-blocked (MATCH verdict), what fraction were genuine hits? Low precision here means blocking legitimate payments.",
    "Block Recall": "Of the highest-confidence real hits, what fraction received a hard block? Low recall means real threats land in review instead of being blocked.",
    "Block F1": "Balanced quality score for the auto-block decision only. Considers both wrongly blocked clean payments and missed hard blocks.",
}


def build_html_report(report_dict: dict) -> str:
    v = report_dict["variants"][0]
    score = _composite_score(v)
    fm = v["flag_metrics"]
    bm = v["block_metrics"]

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    bench_label = Path(report_dict["benchmark_path"]).name
    db_label = Path(report_dict["watchlist_path"]).name

    def pct(val: float) -> str:
        return f"{val * 100:.1f}%"

    def bar(s: float) -> str:
        w = round(s * 100)
        color = "#22c55e" if s >= 0.8 else "#f59e0b" if s >= 0.6 else "#ef4444"
        return (
            f'<div class="bar-wrap">'
            f'<div class="bar" style="width:{w}%;background:{color}"></div>'
            f'<span class="bar-val">{s:.3f}</span>'
            f"</div>"
        )

    def risk_badge(fnr: float) -> str:
        if fnr <= 0.02:
            return '<span class="badge green">LOW RISK</span>'
        if fnr <= 0.08:
            return '<span class="badge amber">MODERATE RISK</span>'
        return '<span class="badge red">HIGH RISK</span>'

    def tip(label: str, key: str | None = None) -> str:
        text = _TIPS.get(key or label, "")
        if not text:
            return label
        safe = text.replace('"', "&quot;")
        return f'<span class="tip" data-tip="{safe}">{label} <sup>?</sup></span>'

    entity_hit = v.get("entity_hit_rate")

    # ── overview card ────────────────────────────────────────────
    overview_html = f"""
    <div class="card best">
      <div class="card-title">v2_cascade</div>
      <div class="card-desc">{v['variant_description']}</div>
      <div class="bar-label">{tip("Composite Score")} = 60% F2 + 40% MCC</div>
      {bar(score)}
      <table class="mini">
        <tr>
          <td>{tip("Detection Rate")}</td>
          <td><strong>{pct(fm['recall'])}</strong></td>
          <td>{tip("Miss Rate")}</td>
          <td class="{'red-txt' if fm['false_negative_rate'] > 0.05 else ''}">{pct(fm['false_negative_rate'])}</td>
        </tr>
        <tr>
          <td>{tip("False Alarm Rate")}</td>
          <td>{pct(fm['false_positive_rate'])}</td>
          <td>{tip("Alert Precision")}</td>
          <td>{pct(fm['precision'])}</td>
        </tr>
        <tr>
          <td>{tip("F2 Score")}</td>
          <td>{fm['f2_score']:.3f}</td>
          <td>{tip("MCC")}</td>
          <td>{fm['mcc']:.3f}</td>
        </tr>
        <tr>
          <td>{tip("Alert Rate")}</td>
          <td>{pct(fm['alert_rate'])}</td>
          <td>{tip("Speed")}</td>
          <td>{v['avg_latency_ms']:.1f} ms</td>
        </tr>
      </table>
      {risk_badge(fm['false_negative_rate'])}
    </div>"""

    # ── metrics table ─────────────────────────────────────────────
    def metric_row(label: str, tip_key: str, val: str) -> str:
        return f"<tr><td class='metric-label'>{tip(label, tip_key)}</td><td>{val}</td></tr>"

    table_html = f"""
    <table class="comparison">
      <thead><tr><th>Metric</th><th>v2_cascade</th></tr></thead>
      <tbody>
        {metric_row("Detection Rate (Recall)", "Detection Rate", pct(fm["recall"]))}
        {metric_row("Miss Rate ← compliance risk", "Miss Rate", pct(fm["false_negative_rate"]))}
        {metric_row("False Alarm Rate", "False Alarm Rate", pct(fm["false_positive_rate"]))}
        {metric_row("Alert Precision", "Alert Precision", pct(fm["precision"]))}
        {metric_row("F2 Score", "F2 Score", f"{fm['f2_score']:.3f}")}
        {metric_row("MCC", "MCC", f"{fm['mcc']:.3f}")}
        {metric_row("F1 Score", "F1 Score", f"{fm['f1_score']:.3f}")}
        {metric_row("Accuracy", "Accuracy", pct(fm["accuracy"]))}
        {metric_row("Alert Rate", "Alert Rate", pct(fm["alert_rate"]))}
        {metric_row("Auto-Block Rate", "Auto-Block Rate", pct(bm["alert_rate"]))}
        {metric_row("Entity Hit Rate", "Entity Hit Rate", pct(entity_hit) if entity_hit is not None else "n/a")}
        {metric_row("Speed (ms / txn)", "Speed", f"{v['avg_latency_ms']:.1f} ms")}
        {metric_row("Block Precision", "Block Precision", pct(bm["precision"]))}
        {metric_row("Block Recall", "Block Recall", pct(bm["recall"]))}
        {metric_row("Block F1", "Block F1", f"{bm['f1_score']:.3f}")}
      </tbody>
    </table>"""

    # ── confusion matrix ─────────────────────────────────────────
    cm_html = f"""
    <div class="cm-block">
      <div class="cm-title">v2_cascade</div>
      <table class="cm">
        <tr>
          <td class="tp">{tip("✔ Correct Alerts", "Correct Alerts (TP)")}<br><strong>{fm['true_positives']}</strong><br><small>(TP)</small></td>
          <td class="fn">{tip("✘ Missed Hits", "Missed Hits (FN)")}<br><strong>{fm['false_negatives']}</strong><br><small>(FN) ← risk</small></td>
        </tr>
        <tr>
          <td class="fp">{tip("⚠ False Alarms", "False Alarms (FP)")}<br><strong>{fm['false_positives']}</strong><br><small>(FP)</small></td>
          <td class="tn">{tip("✔ Clean Passes", "Clean Passes (TN)")}<br><strong>{fm['true_negatives']}</strong><br><small>(TN)</small></td>
        </tr>
      </table>
    </div>"""

    # ── summary box ───────────────────────────────────────────────
    summary_html = f"""
    <div class="winner">
      <div class="winner-title">Engine: v2_cascade</div>
      <p>{v['variant_description']}</p>
      <ul>
        <li>Catches <strong>{pct(fm['recall'])}</strong> of sanctioned entities</li>
        <li>Miss rate of <strong>{pct(fm['false_negative_rate'])}</strong> — {risk_badge(fm['false_negative_rate'])}</li>
        <li><strong>{pct(fm['false_positive_rate'])}</strong> of clean payments wrongly flagged</li>
        <li>Alert queue volume: <strong>{pct(fm['alert_rate'])}</strong> of all transactions</li>
        <li>Composite score: <strong>{score:.3f}</strong> (60% F2 + 40% MCC)</li>
      </ul>
      <div class="config-grid">
        {''.join(f"<div><span>{k}</span><strong>{val}</strong></div>" for k, val in v.get('config', {}).items())}
      </div>
    </div>"""

    css = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f8fafc; color: #1e293b; padding: 32px; }
    h1 { font-size: 1.6rem; font-weight: 700; color: #0f172a; }
    h2 { font-size: 1.1rem; font-weight: 600; color: #334155; margin: 40px 0 16px;
         border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }
    .meta { color: #64748b; font-size: 0.85rem; margin-top: 6px; }
    .cards { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 16px; }
    .card { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; flex: 1; min-width: 220px; }
    .card.best { border-color: #22c55e; box-shadow: 0 0 0 2px #bbf7d0; }
    .card-title { font-size: 1rem; font-weight: 700; margin-bottom: 4px; display: flex; align-items: center; gap: 8px; }
    .card-desc { font-size: 0.8rem; color: #64748b; margin-bottom: 12px; }
    .bar-label { font-size: 0.75rem; color: #94a3b8; margin-bottom: 4px; }
    .bar-wrap { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
    .bar { height: 10px; border-radius: 6px; }
    .bar-val { font-size: 0.85rem; font-weight: 600; color: #334155; }
    .mini { width: 100%; font-size: 0.8rem; border-collapse: collapse; }
    .mini td { padding: 3px 6px; }
    .mini td:nth-child(odd) { color: #64748b; }
    .mini td:nth-child(even) { font-weight: 500; text-align: right; }
    .red-txt { color: #ef4444 !important; }
    .badge { display: inline-block; font-size: 0.7rem; font-weight: 700;
             padding: 2px 8px; border-radius: 99px; margin-top: 10px; }
    .badge.green { background: #dcfce7; color: #166534; }
    .badge.amber { background: #fef9c3; color: #854d0e; }
    .badge.red   { background: #fee2e2; color: #991b1b; }
    .comparison { width: 100%; border-collapse: collapse; font-size: 0.85rem; background: #fff;
                  border: 1px solid #e2e8f0; border-radius: 12px; }
    .comparison th { background: #0f172a; color: #f8fafc; padding: 10px 14px; text-align: left; font-size: 0.8rem; }
    .comparison td { padding: 9px 14px; border-bottom: 1px solid #f1f5f9; }
    .comparison tr:last-child td { border-bottom: none; }
    .comparison tr:hover td { background: #f8fafc; }
    .metric-label { color: #64748b; font-weight: 500; }
    .cm-grid { display: flex; gap: 20px; flex-wrap: wrap; margin-top: 16px; }
    .cm-block { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; }
    .cm-title { font-weight: 600; font-size: 0.9rem; margin-bottom: 12px; color: #334155; }
    .cm { border-collapse: separate; border-spacing: 6px; }
    .cm td { width: 150px; height: 80px; text-align: center; border-radius: 8px;
             font-size: 0.8rem; padding: 8px; cursor: default; }
    .cm td strong { display: block; font-size: 1.4rem; }
    .cm td small { font-size: 0.7rem; color: #64748b; }
    .tp { background: #dcfce7; color: #166534; }
    .tn { background: #dbeafe; color: #1e40af; }
    .fp { background: #fef9c3; color: #854d0e; }
    .fn { background: #fee2e2; color: #991b1b; }
    .winner { background: #0f172a; color: #f8fafc; border-radius: 12px; padding: 28px; margin-top: 16px; }
    .winner-title { font-size: 1.2rem; font-weight: 700; margin-bottom: 12px; color: #22c55e; }
    .winner ul { padding-left: 20px; line-height: 2; }
    .winner li strong { color: #a3e635; }
    .config-grid { display: flex; gap: 24px; flex-wrap: wrap; margin-top: 20px;
                   border-top: 1px solid #334155; padding-top: 16px; }
    .config-grid div { display: flex; flex-direction: column; }
    .config-grid span { font-size: 0.75rem; color: #94a3b8; }
    .config-grid strong { font-size: 0.95rem; color: #f8fafc; }
    footer { text-align: center; color: #94a3b8; font-size: 0.75rem; margin-top: 48px; }

    /* ── tooltips ── */
    .tip { cursor: help; white-space: nowrap; }
    .tip sup { font-size: 0.6rem; color: #94a3b8; margin-left: 1px; }
    #tt {
      position: fixed;
      z-index: 9999;
      background: #1e293b;
      color: #f8fafc;
      font-size: 0.75rem;
      line-height: 1.5;
      padding: 8px 12px;
      border-radius: 8px;
      width: 260px;
      white-space: normal;
      box-shadow: 0 4px 16px rgba(0,0,0,.3);
      pointer-events: none;
      display: none;
    }
    #tt.visible { display: block; }
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sanctions Screening — v2 Report</title>
  <style>{css}</style>
</head>
<body>
  <h1>Sanctions Screening — v2 Performance Report</h1>
  <p class="meta">Generated: {generated} &nbsp;|&nbsp; Benchmark: {bench_label} ({report_dict['case_count']} cases) &nbsp;|&nbsp; Watchlist: {db_label}</p>

  <h2>Engine Overview</h2>
  <p style="font-size:0.8rem;color:#64748b;margin-bottom:8px">
    {tip("Composite Score")} = 60% F2 (recall-weighted) + 40% MCC (robust for imbalanced data) &nbsp;·&nbsp; Hover any metric label for a plain-English explanation.
  </p>
  <div class="cards">{overview_html}</div>

  <h2>Metrics</h2>
  {table_html}

  <h2>Confusion Matrix</h2>
  <p style="font-size:0.8rem;color:#64748b;margin-bottom:12px">Hover each cell label for an explanation. MATCH + REVIEW both count as flagged.</p>
  <div class="cm-grid">{cm_html}</div>

  <h2>Summary</h2>
  {summary_html}

  <footer>TeslaFinTech Sanctions Screening &nbsp;·&nbsp; {generated}</footer>
</body>
<div id="tt"></div>
<script>
  const tt = document.getElementById('tt');
  const PAD = 12;

  document.querySelectorAll('.tip').forEach(el => {{
    el.addEventListener('mouseenter', e => {{
      tt.textContent = el.dataset.tip;
      tt.classList.add('visible');
      position(e);
    }});
    el.addEventListener('mousemove', position);
    el.addEventListener('mouseleave', () => tt.classList.remove('visible'));
  }});

  function position(e) {{
    const W = tt.offsetWidth, H = tt.offsetHeight;
    let x = e.clientX - W / 2;
    let y = e.clientY - H - 14;

    // flip below cursor if too close to top
    if (y < PAD) y = e.clientY + 20;

    // clamp horizontally so it never leaves the viewport
    x = Math.max(PAD, Math.min(x, window.innerWidth - W - PAD));

    tt.style.left = x + 'px';
    tt.style.top  = y + 'px';
  }}
</script>
</html>"""


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a v2 screening performance report.")
    parser.add_argument("--benchmark", type=Path, default=None, help="Path to benchmark JSON.")
    parser.add_argument("--db", type=Path, default=None, help="Path to AML SQLite database.")
    parser.add_argument("--output", type=Path, default=None, help="File path for the saved text report.")
    parser.add_argument("--no-save", action="store_true", help="Print only, do not save to file.")
    parser.add_argument("--html-only", action="store_true", help="Save HTML only, skip console output.")
    args = parser.parse_args()

    print("Running evaluation…", file=sys.stderr)
    pipeline = ABTestPipeline.from_db(args.benchmark, args.db)
    report_dict = pipeline.run_ab_test(default_variants()).model_dump(mode="json")

    report_text = build_report(report_dict)

    if not args.html_only:
        print(report_text)

    if not args.no_save:
        reports_dir = (args.output.parent if args.output else Path("reports"))
        reports_dir.mkdir(parents=True, exist_ok=True)

        txt_path = args.output or reports_dir / "screening_report.txt"
        txt_path.write_text(report_text, encoding="utf-8")
        print(f"Text report  → {txt_path}", file=sys.stderr)

        html_path = txt_path.with_suffix(".html")
        html_path.write_text(build_html_report(report_dict), encoding="utf-8")
        print(f"HTML report  → {html_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
