from __future__ import annotations

import math

from screening.evaluation.models import ClassificationMetrics
from screening.models import ScreeningVerdict


def is_flagged(verdict: ScreeningVerdict) -> bool:
    return verdict in {ScreeningVerdict.MATCH, ScreeningVerdict.REVIEW}


def is_blocked(verdict: ScreeningVerdict) -> bool:
    return verdict == ScreeningVerdict.MATCH


def compute_metrics(
    y_true: list[bool],
    y_pred: list[bool],
) -> ClassificationMetrics:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same length.")
    if not y_true:
        return _empty_metrics()

    tp = sum(1 for truth, pred in zip(y_true, y_pred) if truth and pred)
    tn = sum(1 for truth, pred in zip(y_true, y_pred) if not truth and not pred)
    fp = sum(1 for truth, pred in zip(y_true, y_pred) if not truth and pred)
    fn = sum(1 for truth, pred in zip(y_true, y_pred) if truth and not pred)

    total = tp + tn + fp + fn
    accuracy = _safe_div(tp + tn, total)

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1_score = _safe_div(2 * precision * recall, precision + recall)

    # F2: weights recall twice as heavily as precision.
    # Standard in AML/sanctions where missing a hit (FN) is far costlier than a false alarm.
    f2_score = _safe_div(5 * precision * recall, 4 * precision + recall)

    # MCC: robust single-number quality score for imbalanced datasets (range -1 to +1).
    mcc_denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = _safe_div(tp * tn - fp * fn, mcc_denom)

    specificity = _safe_div(tn, tn + fp)
    false_positive_rate = _safe_div(fp, fp + tn)
    false_negative_rate = _safe_div(fn, fn + tp)
    alert_rate = _safe_div(tp + fp, total)

    return ClassificationMetrics(
        true_positives=tp,
        true_negatives=tn,
        false_positives=fp,
        false_negatives=fn,
        accuracy=round(accuracy, 4),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1_score, 4),
        f2_score=round(f2_score, 4),
        mcc=round(mcc, 4),
        specificity=round(specificity, 4),
        false_positive_rate=round(false_positive_rate, 4),
        false_negative_rate=round(false_negative_rate, 4),
        alert_rate=round(alert_rate, 4),
        support_positive=tp + fn,
        support_negative=tn + fp,
    )


def compute_verdict_metrics(
    y_true: list[ScreeningVerdict],
    y_pred: list[ScreeningVerdict],
) -> dict:
    labels = [
        ScreeningVerdict.MATCH,
        ScreeningVerdict.REVIEW,
        ScreeningVerdict.NO_MATCH,
    ]
    per_class: dict[str, dict[str, float]] = {}
    precisions: list[float] = []
    recalls: list[float] = []
    f1s: list[float] = []
    weights: list[int] = []

    for label in labels:
        tp = sum(1 for truth, pred in zip(y_true, y_pred) if truth == label and pred == label)
        fp = sum(1 for truth, pred in zip(y_true, y_pred) if truth != label and pred == label)
        fn = sum(1 for truth, pred in zip(y_true, y_pred) if truth == label and pred != label)
        support = sum(1 for truth in y_true if truth == label)

        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * precision * recall, precision + recall)

        per_class[label.value] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "support": support,
        }
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)
        weights.append(support)

    total = len(y_true)
    weighted_precision = _weighted_average(
        [per_class[label.value]["precision"] for label in labels],
        weights,
    )
    weighted_recall = _weighted_average(
        [per_class[label.value]["recall"] for label in labels],
        weights,
    )
    weighted_f1 = _weighted_average(
        [per_class[label.value]["f1_score"] for label in labels],
        weights,
    )

    correct = sum(1 for truth, pred in zip(y_true, y_pred) if truth == pred)

    return {
        "macro_precision": round(_mean(precisions), 4),
        "macro_recall": round(_mean(recalls), 4),
        "macro_f1": round(_mean(f1s), 4),
        "weighted_precision": round(weighted_precision, 4),
        "weighted_recall": round(weighted_recall, 4),
        "weighted_f1": round(weighted_f1, 4),
        "verdict_accuracy": round(_safe_div(correct, total), 4),
        "per_class": per_class,
    }


def _empty_metrics() -> ClassificationMetrics:
    return ClassificationMetrics(
        true_positives=0,
        true_negatives=0,
        false_positives=0,
        false_negatives=0,
        accuracy=0.0,
        precision=0.0,
        recall=0.0,
        f1_score=0.0,
        f2_score=0.0,
        mcc=0.0,
        specificity=0.0,
        false_positive_rate=0.0,
        false_negative_rate=0.0,
        alert_rate=0.0,
        support_positive=0,
        support_negative=0,
    )


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _weighted_average(values: list[float], weights: list[int]) -> float:
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0
    return sum(value * weight for value, weight in zip(values, weights)) / total_weight
