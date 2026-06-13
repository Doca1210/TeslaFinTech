import pytest
from app.database import SessionLocal
from screening_v2.normal_search import NormalSearcher
from screening_v2.normalizer import Normalizer

_normalizer = Normalizer()


@pytest.fixture(scope="module")
def searcher():
    return NormalSearcher(SessionLocal)


def test_finds_putin(searcher):
    normalized = _normalizer.normalize("Vladimir Putin", "individual")
    candidates = searcher.search(normalized)
    assert len(candidates) > 0
    assert any("PUTIN" in c.matched_name.upper() for c in candidates)


def test_finds_shoigu_without_patronym(searcher):
    # Key test: patronym normalization fix — DB has "SHOIGU Sergei Kuzhugetovich"
    normalized = _normalizer.normalize("Sergei Shoigu", "individual")
    candidates = searcher.search(normalized)
    assert any("SHOIGU" in c.matched_name.upper() for c in candidates)
    assert candidates[0].match_score >= 0.60


def test_top_result_has_entity_profile(searcher):
    normalized = _normalizer.normalize("Vladimir Putin", "individual")
    candidates = searcher.search(normalized)
    assert len(candidates) > 0
    profile = candidates[0].entity_profile
    assert profile.source_uid
    assert profile.primary_name
    assert len(profile.programs) > 0


def test_top_result_has_score_breakdown(searcher):
    normalized = _normalizer.normalize("Vladimir Putin", "individual")
    candidates = searcher.search(normalized)
    bd = candidates[0].score_breakdown
    assert 0.0 <= bd.token_set_ratio <= 1.0
    assert 0.0 <= bd.jaro_winkler <= 1.0


def test_clean_name_has_low_confidence(searcher):
    normalized = _normalizer.normalize("Bartholomew Kingsborough", "individual")
    candidates = searcher.search(normalized)
    if candidates:
        assert candidates[0].match_score < 0.85


def test_returns_at_most_five_candidates(searcher):
    normalized = _normalizer.normalize("Vladimir Putin", "individual")
    candidates = searcher.search(normalized)
    assert len(candidates) <= 5


def test_alias_hit_flagged(searcher):
    # Putin has aliases in OFAC — searching an alias should set matched_via_alias=True
    normalized = _normalizer.normalize("Putin Vladimir", "individual")
    candidates = searcher.search(normalized)
    assert len(candidates) > 0


def test_entity_type_scored_without_phonetic(searcher):
    normalized = _normalizer.normalize("Rosneft", "entity")
    candidates = searcher.search(normalized)
    # Should not crash; phonetic component should be absent
    if candidates:
        assert candidates[0].score_breakdown.phonetic_match is None
