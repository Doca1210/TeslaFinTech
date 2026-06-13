from __future__ import annotations

import jellyfish

# Particles stripped before per-token fuzzy checks (Arabic/Romance/Western).
NAME_PARTICLES = frozenset({"al", "el", "ib", "bin", "von", "de", "del", "la", "le", "van", "der"})

VECTOR_MIN_FUZZY = 0.62
TOKEN_MATCH_THRESHOLD = 0.82


def significant_tokens(text: str) -> list[str]:
    return [t for t in text.split() if t and t not in NAME_PARTICLES]


def token_coverage(query: str, candidate: str) -> float:
    """Fraction of tokens matched on both sides (exact token overlap)."""
    query_tokens = set(significant_tokens(query))
    candidate_tokens = set(significant_tokens(candidate))
    if not query_tokens or not candidate_tokens:
        return 0.0
    overlap = query_tokens & candidate_tokens
    if not overlap:
        return 0.0
    return min(len(overlap) / len(query_tokens), len(overlap) / len(candidate_tokens))


def all_significant_tokens_match(
    query: str,
    candidate: str,
    threshold: float = TOKEN_MATCH_THRESHOLD,
) -> bool:
    """Each significant query token must fuzzy-match some candidate token."""
    query_tokens = significant_tokens(query)
    candidate_tokens = significant_tokens(candidate)
    if len(query_tokens) < 2:
        return True
    if not candidate_tokens:
        return False
    for query_token in query_tokens:
        best = max(
            jellyfish.jaro_winkler_similarity(query_token, candidate_token)
            for candidate_token in candidate_tokens
        )
        if best < threshold:
            return False
    return True


def apply_entity_coverage_penalty(score: float, query: str, candidate: str) -> float:
    """Down-rank entity hits that share only one generic token (e.g. 'logistics')."""
    if len(significant_tokens(query)) <= 1:
        return score
    coverage = token_coverage(query, candidate)
    if coverage >= 1.0:
        return score
    return score * coverage


def reorder_resistant_similarity(query: str, candidate: str) -> float:
    """Jaro-Winkler that stays high when the same tokens appear in different order."""
    direct = jellyfish.jaro_winkler_similarity(query, candidate)
    query_sorted = " ".join(sorted(query.split()))
    candidate_sorted = " ".join(sorted(candidate.split()))
    return max(direct, jellyfish.jaro_winkler_similarity(query_sorted, candidate_sorted))

