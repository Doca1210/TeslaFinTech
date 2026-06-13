from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from screening.models import ScreeningVerdict, Transaction


class ExpectedLabel(str, Enum):
    """Whether a transaction should be flagged by screening."""

    POSITIVE = "positive"
    NEGATIVE = "negative"


class BenchmarkCase(BaseModel):
    case_id: str
    transaction_id: str
    counterparty_name: str
    counterparty_country: str | None = None
    label: ExpectedLabel
    expected_verdict: ScreeningVerdict | None = None
    expected_entity_id: str | None = None
    category: str = "general"
    notes: str | None = None

    def to_transaction(self) -> Transaction:
        return Transaction(
            transaction_id=self.transaction_id,
            counterparty_name=self.counterparty_name,
            counterparty_country=self.counterparty_country,
        )

    @property
    def should_flag(self) -> bool:
        return self.label == ExpectedLabel.POSITIVE


class CasePrediction(BaseModel):
    case_id: str
    predicted_verdict: ScreeningVerdict
    predicted_flagged: bool
    confidence: float
    predicted_entity_id: str | None = None
    expected_label: ExpectedLabel
    expected_verdict: ScreeningVerdict | None = None
    expected_entity_id: str | None = None
    category: str
    correct_flag: bool
    correct_verdict: bool | None = None
    correct_entity: bool | None = None


class ClassificationMetrics(BaseModel):
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    f2_score: float        # recall-weighted F score (standard in high-stakes screening)
    mcc: float             # Matthews Correlation Coefficient — robust for imbalanced data
    specificity: float
    false_positive_rate: float
    false_negative_rate: float
    alert_rate: float      # fraction of cases flagged (MATCH + REVIEW)
    support_positive: int
    support_negative: int


class VerdictMetrics(BaseModel):
    """Multi-class metrics over MATCH / REVIEW / NO_MATCH."""

    macro_precision: float
    macro_recall: float
    macro_f1: float
    weighted_precision: float
    weighted_recall: float
    weighted_f1: float
    verdict_accuracy: float
    per_class: dict[str, dict[str, float]]


class VariantEvaluation(BaseModel):
    variant_name: str
    variant_description: str
    config: dict
    case_count: int
    flag_metrics: ClassificationMetrics
    block_metrics: ClassificationMetrics
    entity_hit_rate: float | None = None
    entity_cases: int = 0
    verdict_metrics: VerdictMetrics | None = None
    avg_latency_ms: float
    predictions: list[CasePrediction] = Field(default_factory=list)


class BenchmarkReport(BaseModel):
    benchmark_path: str
    watchlist_path: str
    case_count: int
    variants: list[VariantEvaluation]
    winner_by_flag_f1: str
    winner_by_block_f1: str
    winner_by_verdict_macro_f1: str | None = None
