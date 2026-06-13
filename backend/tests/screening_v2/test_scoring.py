import jellyfish

from screening_v2.scoring import (
    all_significant_tokens_match,
    apply_entity_coverage_penalty,
    significant_tokens,
    token_coverage,
)


def test_significant_tokens_strips_particles():
    assert significant_tokens("muammar al qadhafi") == ["muammar", "qadhafi"]


def test_token_coverage_partial_entity_overlap():
    assert token_coverage("acme supplies", "military supplies industry") == 1 / 3


def test_token_coverage_full_match():
    assert token_coverage("vladimir putin", "vladimir putin") == 1.0


def test_all_tokens_match_rejects_shared_first_name_only():
    assert not all_significant_tokens_match("vladimir petrov", "vladimir putin")


def test_all_tokens_match_accepts_transliteration():
    assert all_significant_tokens_match("muammar qadhafi", "muammar gadhafi")


def test_all_tokens_match_accepts_reordered_name():
    assert all_significant_tokens_match("shoigu sergei", "sergei shoigu")


def test_all_tokens_match_rejects_shared_surname_only():
    assert not all_significant_tokens_match("kim lee", "john lee")


def test_entity_coverage_penalty_downranks_single_token_hit():
    penalized = apply_entity_coverage_penalty(0.75, "nordic freight solutions", "vfc solutions")
    assert penalized < 0.30


def test_reorder_resistant_similarity_handles_reversed_names():
    from screening_v2.scoring import reorder_resistant_similarity

    assert reorder_resistant_similarity("shoigu sergei", "sergei shoigu") >= 0.95
    assert reorder_resistant_similarity("lavrov sergei", "sergei lavrov") >= 0.95


def test_entity_coverage_penalty_skips_single_token_query():
    assert apply_entity_coverage_penalty(0.95, "rosneft", "rosneft trading sa") == 0.95

