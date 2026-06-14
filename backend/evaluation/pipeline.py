from __future__ import annotations

import time
from pathlib import Path

from evaluation.benchmark_loader import default_benchmark_path, default_db_path, load_benchmark
from evaluation.metrics import (
    compute_metrics,
    compute_verdict_metrics,
    is_blocked,
    is_flagged,
)
from evaluation.models import (
    BenchmarkCase,
    BenchmarkReport,
    CasePrediction,
    ScreeningVerdict,
    VariantEvaluation,
    VerdictMetrics,
)
from evaluation.variants import AlgorithmVariant, default_variants


class ABTestPipeline:
    """Run labeled benchmark cases against multiple screening variants."""

    def __init__(
        self,
        watchlist: list,
        cases: list[BenchmarkCase],
        *,
        benchmark_path: Path | str | None = None,
        watchlist_path: Path | str | None = None,
    ) -> None:
        self.watchlist = watchlist
        self.cases = cases
        self.benchmark_path = str(benchmark_path or default_benchmark_path())
        self.watchlist_path = str(watchlist_path or default_db_path())

    @classmethod
    def from_db(
        cls,
        benchmark_path: Path | str | None = None,
        db_path: Path | str | None = None,
    ) -> "ABTestPipeline":
        db = Path(db_path or default_db_path())
        bench_path = Path(benchmark_path or default_benchmark_path())
        return cls(
            watchlist=[],
            cases=load_benchmark(bench_path),
            benchmark_path=bench_path,
            watchlist_path=db,
        )

    def evaluate_variant(self, variant: AlgorithmVariant) -> VariantEvaluation:
        engine = variant.factory(self.watchlist)
        predictions: list[CasePrediction] = []
        latencies_ms: list[float] = []

        for case in self.cases:
            start = time.perf_counter()
            result = engine.screen(case.to_transaction())
            latencies_ms.append((time.perf_counter() - start) * 1000)
            predictions.append(self._to_prediction(case, result))

        flag_metrics = compute_metrics(
            [case.should_flag for case in self.cases],
            [prediction.predicted_flagged for prediction in predictions],
        )
        block_metrics = compute_metrics(
            [self._should_block(case) for case in self.cases],
            [is_blocked(prediction.predicted_verdict) for prediction in predictions],
        )

        entity_predictions = [p for p in predictions if p.expected_entity_id is not None]
        entity_hit_rate = None
        if entity_predictions:
            hits = sum(1 for p in entity_predictions if p.correct_entity)
            entity_hit_rate = round(hits / len(entity_predictions), 4)

        verdict_cases = [case for case in self.cases if case.expected_verdict is not None]
        verdict_metrics = None
        if verdict_cases:
            case_ids = {case.case_id for case in verdict_cases}
            subset = [p for p in predictions if p.case_id in case_ids]
            raw = compute_verdict_metrics(
                [p.expected_verdict for p in subset if p.expected_verdict is not None],
                [p.predicted_verdict for p in subset],
            )
            verdict_metrics = VerdictMetrics(**raw)

        return VariantEvaluation(
            variant_name=variant.name,
            variant_description=variant.description,
            config=variant.config,
            case_count=len(self.cases),
            flag_metrics=flag_metrics,
            block_metrics=block_metrics,
            entity_hit_rate=entity_hit_rate,
            entity_cases=len(entity_predictions),
            verdict_metrics=verdict_metrics,
            avg_latency_ms=round(sum(latencies_ms) / len(latencies_ms), 3),
            predictions=predictions,
        )

    def run_ab_test(
        self,
        variants: list[AlgorithmVariant] | None = None,
    ) -> BenchmarkReport:
        variant_list = variants or default_variants()
        evaluations = [self.evaluate_variant(variant) for variant in variant_list]

        return BenchmarkReport(
            benchmark_path=self.benchmark_path,
            watchlist_path=self.watchlist_path,
            case_count=len(self.cases),
            variants=evaluations,
            winner_by_flag_f1=_pick_winner(evaluations, "flag"),
            winner_by_block_f1=_pick_winner(evaluations, "block"),
            winner_by_verdict_macro_f1=_pick_winner(evaluations, "verdict"),
        )

    @staticmethod
    def _should_block(case: BenchmarkCase) -> bool:
        if case.expected_verdict is not None:
            return case.expected_verdict == ScreeningVerdict.MATCH
        return case.should_flag

    @staticmethod
    def _to_prediction(case: BenchmarkCase, result) -> CasePrediction:
        predicted_entity_id = (
            result.matched_entities[0].entity.id if result.matched_entities else None
        )
        predicted_flagged = is_flagged(result.verdict)

        correct_verdict = None
        if case.expected_verdict is not None:
            correct_verdict = result.verdict == case.expected_verdict

        correct_entity = None
        if case.expected_entity_id is not None:
            correct_entity = predicted_entity_id == case.expected_entity_id

        return CasePrediction(
            case_id=case.case_id,
            predicted_verdict=result.verdict,
            predicted_flagged=predicted_flagged,
            confidence=result.confidence,
            predicted_entity_id=predicted_entity_id,
            expected_label=case.label,
            expected_verdict=case.expected_verdict,
            expected_entity_id=case.expected_entity_id,
            category=case.category,
            correct_flag=predicted_flagged == case.should_flag,
            correct_verdict=correct_verdict,
            correct_entity=correct_entity,
        )


def _pick_winner(evaluations: list[VariantEvaluation], mode: str) -> str:
    if not evaluations:
        return ""

    if mode == "flag":
        return max(evaluations, key=lambda item: item.flag_metrics.f1_score).variant_name
    if mode == "block":
        return max(evaluations, key=lambda item: item.block_metrics.f1_score).variant_name
    if mode == "verdict":
        scored = [
            item for item in evaluations if item.verdict_metrics is not None
        ]
        if not scored:
            return ""
        return max(
            scored,
            key=lambda item: item.verdict_metrics.macro_f1 if item.verdict_metrics else 0.0,
        ).variant_name
    raise ValueError(f"Unknown winner mode: {mode}")
