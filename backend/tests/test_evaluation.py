import json
from pathlib import Path

from evaluation.metrics import compute_metrics, is_flagged
from evaluation.models import BenchmarkCase, ExpectedLabel, ScreeningVerdict
from evaluation.pipeline import ABTestPipeline
from evaluation.variants import default_variants, get_variant


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


def test_v2_pipeline_runs():
    pipeline = ABTestPipeline.from_db()
    report = pipeline.run_ab_test(default_variants())

    assert report.case_count >= 10
    assert len(report.variants) == 1
    assert report.variants[0].variant_name == "v2_cascade"

    for evaluation in report.variants:
        assert evaluation.flag_metrics.support_positive > 0
        assert evaluation.flag_metrics.support_negative > 0
        assert 0.0 <= evaluation.flag_metrics.f1_score <= 1.0


def test_evaluate_cli_output_json(tmp_path: Path):
    output = tmp_path / "report.json"
    pipeline = ABTestPipeline.from_db()
    report = pipeline.run_ab_test([get_variant("v2_cascade")])
    output.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["case_count"] > 0
    assert payload["variants"][0]["flag_metrics"]["f1_score"] >= 0.0


def test_is_flagged_mapping():
    assert is_flagged(ScreeningVerdict.MATCH) is True
    assert is_flagged(ScreeningVerdict.REVIEW) is True
    assert is_flagged(ScreeningVerdict.NO_MATCH) is False


def test_expected_label_positive():
    case = BenchmarkCase(
        case_id="x",
        transaction_id="t",
        counterparty_name="Test",
        label=ExpectedLabel.POSITIVE,
    )
    assert case.should_flag is True
