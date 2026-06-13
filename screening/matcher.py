from __future__ import annotations

import jellyfish
from rapidfuzz import fuzz

from screening.models import MatchSignal, WatchlistEntity
from screening.normalizer import (
    is_common_name,
    normalize_text,
    token_sort_key,
    tokenize,
)


class NameMatcher:
    """Hybrid fuzzy + phonetic matcher tuned for PEP/sanctions-style name screening."""

    def __init__(
        self,
        *,
        match_threshold: float = 92.0,
        review_threshold: float = 78.0,
        country_boost: float = 5.0,
        common_name_penalty: float = 12.0,
    ) -> None:
        self.match_threshold = match_threshold
        self.review_threshold = review_threshold
        self.country_boost = country_boost
        self.common_name_penalty = common_name_penalty

    def compare(
        self,
        query_name: str,
        entity: WatchlistEntity,
        query_country: str | None = None,
    ) -> tuple[float, list[MatchSignal]]:
        candidate_names = [entity.full_name, *entity.aliases]
        best_score = 0.0
        best_signals: list[MatchSignal] = []

        for candidate in candidate_names:
            score, signals = self._score_pair(query_name, candidate)
            if query_country and entity.country:
                if query_country.upper() == entity.country.upper():
                    score = min(100.0, score + self.country_boost)
                    signals.append(
                        MatchSignal(
                            name=candidate,
                            score=score,
                            method="country",
                            detail=f"Country match: {entity.country}",
                        )
                    )
            if score > best_score:
                best_score = score
                best_signals = signals

        if is_common_name(query_name) and best_score < 98.0:
            best_score = max(0.0, best_score - self.common_name_penalty)
            best_signals.append(
                MatchSignal(
                    name=query_name,
                    score=best_score,
                    method="common_name_penalty",
                    detail="Common name tokens reduced confidence",
                )
            )

        return round(best_score, 2), best_signals

    def _score_pair(self, query_name: str, candidate_name: str) -> tuple[float, list[MatchSignal]]:
        signals: list[MatchSignal] = []

        exact_norm = normalize_text(query_name) == normalize_text(candidate_name)
        if exact_norm:
            return 100.0, [
                MatchSignal(
                    name=candidate_name,
                    score=100.0,
                    method="exact",
                    detail="Normalized exact match",
                )
            ]

        token_set = float(fuzz.token_set_ratio(query_name, candidate_name))
        token_sort = float(fuzz.token_sort_ratio(query_name, candidate_name))
        partial = float(fuzz.partial_ratio(query_name, candidate_name))
        wratio = float(fuzz.WRatio(query_name, candidate_name))

        phonetic = self._phonetic_score(query_name, candidate_name)

        # Weighted blend favors token-aware scores over naive substring hits.
        blended = (
            0.30 * token_set
            + 0.25 * token_sort
            + 0.20 * wratio
            + 0.15 * partial
            + 0.10 * phonetic
        )

        if token_sort_key(query_name) == token_sort_key(candidate_name):
            blended = min(100.0, blended + 8.0)
            signals.append(
                MatchSignal(
                    name=candidate_name,
                    score=blended,
                    method="token_order",
                    detail="Same tokens in different order",
                )
            )

        signals.extend(
            [
                MatchSignal(
                    name=candidate_name,
                    score=token_set,
                    method="token_set",
                    detail="Token overlap similarity",
                ),
                MatchSignal(
                    name=candidate_name,
                    score=token_sort,
                    method="token_sort",
                    detail="Sorted token similarity",
                ),
                MatchSignal(
                    name=candidate_name,
                    score=phonetic,
                    method="phonetic",
                    detail="Soundex/Metaphone token overlap",
                ),
            ]
        )

        return round(blended, 2), signals

    def _phonetic_score(self, left: str, right: str) -> float:
        left_codes = {self._phonetic_codes(token) for token in tokenize(left)}
        right_codes = {self._phonetic_codes(token) for token in tokenize(right)}
        if not left_codes or not right_codes:
            return 0.0

        overlap = len(left_codes & right_codes)
        union = len(left_codes | right_codes)
        return round(100.0 * overlap / union, 2)

    @staticmethod
    def _phonetic_codes(token: str) -> frozenset[str]:
        return frozenset(
            {
                jellyfish.soundex(token),
                jellyfish.metaphone(token),
                jellyfish.nysiis(token),
            }
        )
