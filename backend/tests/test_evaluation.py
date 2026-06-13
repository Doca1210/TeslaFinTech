import json
from pathlib import Path

from screening.evaluation.metrics import compute_metrics, is_flagged
from screening.evaluation.models import ExpectedLabel
from screening.evaluation.pipeline import ABTestPipeline
from screening.evaluation.variants import default_variants, get_variant
from screening.models import ScreeningVerdict


def test_compute_metrics_perfect_classifier():
    y_true = [True, True, False, False]
    y_pred = [True, True, False, False]
    metrics = compute_metrics(y_true, y_pred)

    assert metrics.accuracy == 1.0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1_score == 1.0
    assert metrics.true_positives == 2
    assert metrics.true_negatives == 2


def test_compute_metrics_mixed():
    y_true = [True, True, False, False, True]
    y_pred = [True, False, False, True, True]
    metrics = compute_metrics(y_true, y_pred)

    assert metrics.true_positives == 2
    assert metrics.false_negatives == 1
    assert metrics.false_positives == 1
    assert metrics.true_negatives == 1
    assert metrics.accuracy == 0.6


def test_ab_pipeline_runs_all_variants():
    pipeline = ABTestPipeline.from_paths()
    report = pipeline.run_ab_test(default_variants())

    assert report.case_count >= 10
    assert len(report.variants) == 4
    assert report.winner_by_flag_f1

    for evaluation in report.variants:
        assert evaluation.flag_metrics.support_positive > 0
        assert evaluation.flag_metrics.support_negative > 0
        assert 0.0 <= evaluation.flag_metrics.f1_score <= 1.0


def test_hybrid_default_beats_baseline_on_recall():
    pipeline = ABTestPipeline.from_paths()
    report = pipeline.run_ab_test(
        [get_variant("hybrid_default"), get_variant("token_set_baseline")]
    )

    by_name = {item.variant_name: item for item in report.variants}
    hybrid = by_name["hybrid_default"]
    baseline = by_name["token_set_baseline"]

    assert hybrid.flag_metrics.recall >= baseline.flag_metrics.recall


def test_evaluate_cli_output_json(tmp_path: Path):
    output = tmp_path / "report.json"
    pipeline = ABTestPipeline.from_paths()
    report = pipeline.run_ab_test([get_variant("hybrid_default")])
    output.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["case_count"] > 0
    assert payload["variants"][0]["flag_metrics"]["f1_score"] >= 0.0


def test_is_flagged_mapping():
    assert is_flagged(ScreeningVerdict.MATCH) is True
    assert is_flagged(ScreeningVerdict.REVIEW) is True
    assert is_flagged(ScreeningVerdict.NO_MATCH) is False


def test_expected_label_positive():
    from screening.evaluation.models import BenchmarkCase

    case = BenchmarkCase(
        case_id="x",
        transaction_id="t",
        counterparty_name="Test",
        label=ExpectedLabel.POSITIVE,
    )
    assert case.should_flag is True
