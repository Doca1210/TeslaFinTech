from __future__ import annotations

from rapidfuzz import fuzz
from rapidfuzz import process as fuzz_process

from screening.matcher import NameMatcher
from screening.models import (
    MatchedEntity,
    ScreeningResult,
    ScreeningVerdict,
    Transaction,
    WatchlistEntity,
)

# Conservative pre-filter threshold: low enough to never drop a real candidate,
# high enough to eliminate ~95% of the watchlist before expensive scoring.
_BLOCK_CUTOFF = 55.0
_BLOCK_LIMIT = 300


class ScreeningEngine:
    """Screen incoming transactions against PEP / watchlist entities."""

    def __init__(
        self,
        watchlist: list[WatchlistEntity],
        *,
        matcher: NameMatcher | None = None,
        match_threshold: float = 92.0,
        review_threshold: float = 78.0,
        max_results: int = 5,
    ) -> None:
        self.watchlist = watchlist
        self.matcher = matcher or NameMatcher(
            match_threshold=match_threshold,
            review_threshold=review_threshold,
        )
        self.match_threshold = match_threshold
        self.review_threshold = review_threshold
        self.max_results = max_results

        # Flat name index for fast C-level blocking before expensive scoring.
        self._name_index: list[str] = []
        self._name_to_entity: list[int] = []
        for i, entity in enumerate(watchlist):
            for name in [entity.full_name, *entity.aliases]:
                if name:
                    self._name_index.append(name)
                    self._name_to_entity.append(i)

    def screen(self, transaction: Transaction) -> ScreeningResult:
        matches: list[MatchedEntity] = []

        # Fast C-level blocking pass — narrows 7k+ entities to ~10-50 candidates.
        raw_hits = fuzz_process.extract(
            transaction.counterparty_name,
            self._name_index,
            scorer=fuzz.token_set_ratio,
            score_cutoff=_BLOCK_CUTOFF,
            limit=_BLOCK_LIMIT,
        )
        candidate_indices = {self._name_to_entity[hit[2]] for hit in raw_hits}

        for idx in candidate_indices:
            entity = self.watchlist[idx]
            confidence, signals = self.matcher.compare(
                transaction.counterparty_name,
                entity,
                transaction.counterparty_country,
            )
            if confidence >= self.review_threshold:
                matches.append(
                    MatchedEntity(
                        entity=entity,
                        confidence=confidence,
                        signals=signals,
                    )
                )

        matches.sort(key=lambda item: item.confidence, reverse=True)
        top_matches = matches[: self.max_results]

        if not top_matches:
            return ScreeningResult(
                transaction_id=transaction.transaction_id,
                verdict=ScreeningVerdict.NO_MATCH,
                confidence=0.0,
                counterparty_name=transaction.counterparty_name,
                counterparty_country=transaction.counterparty_country,
                matched_entities=[],
                explanation="No watchlist entity exceeded the review threshold.",
                audit=self._audit_payload(transaction, top_matches),
            )

        best = top_matches[0]
        verdict = self._verdict_for_score(best.confidence)

        return ScreeningResult(
            transaction_id=transaction.transaction_id,
            verdict=verdict,
            confidence=best.confidence,
            counterparty_name=transaction.counterparty_name,
            counterparty_country=transaction.counterparty_country,
            matched_entities=top_matches,
            explanation=self._build_explanation(transaction, best, verdict),
            audit=self._audit_payload(transaction, top_matches),
        )

    def screen_batch(self, transactions: list[Transaction]) -> list[ScreeningResult]:
        return [self.screen(transaction) for transaction in transactions]

    def _verdict_for_score(self, confidence: float) -> ScreeningVerdict:
        if confidence >= self.match_threshold:
            return ScreeningVerdict.MATCH
        if confidence >= self.review_threshold:
            return ScreeningVerdict.REVIEW
        return ScreeningVerdict.NO_MATCH

    def _build_explanation(
        self,
        transaction: Transaction,
        best_match: MatchedEntity,
        verdict: ScreeningVerdict,
    ) -> str:
        entity = best_match.entity
        methods = sorted({signal.method for signal in best_match.signals})
        method_text = ", ".join(methods)

        action = {
            ScreeningVerdict.MATCH: "Block payment and escalate to compliance.",
            ScreeningVerdict.REVIEW: "Route to analyst queue for manual review.",
            ScreeningVerdict.NO_MATCH: "Release payment.",
        }[verdict]

        return (
            f"{verdict.value}: '{transaction.counterparty_name}' matched "
            f"'{entity.full_name}' ({entity.list_source}/{entity.risk_category}) "
            f"with {best_match.confidence:.1f}% confidence. "
            f"Signals: {method_text}. {action}"
        )

    def _audit_payload(
        self,
        transaction: Transaction,
        matches: list[MatchedEntity],
    ) -> dict:
        return {
            "thresholds": {
                "match": self.match_threshold,
                "review": self.review_threshold,
            },
            "watchlist_size": len(self.watchlist),
            "query": {
                "name": transaction.counterparty_name,
                "country": transaction.counterparty_country,
            },
            "candidate_count": len(matches),
            "top_match_id": matches[0].entity.id if matches else None,
        }
