import pytest
from app.database import SessionLocal
from screening_v2.vector_search import VectorSearcher
from screening_v2.normalizer import Normalizer
from screening_v2.db_helpers import load_all_profiles

_normalizer = Normalizer()


@pytest.fixture(scope="module")
def searcher():
    profile_cache = load_all_profiles(SessionLocal)
    return VectorSearcher(SessionLocal, profile_cache=profile_cache)


def test_finds_transliteration_variant(searcher):
    # "Shoygu" is an alternate Latin spelling of "Shoigu"
    normalized = _normalizer.normalize("Sergey Shoygu", "individual")
    candidates = searcher.search(normalized, normal_candidates=[])
    assert any("SHOIGU" in c.matched_name.upper() for c in candidates)


def test_finds_cyrillic_name(searcher):
    normalized = _normalizer.normalize("Владимир Путин", "individual")
    candidates = searcher.search(normalized, normal_candidates=[])
    assert len(candidates) > 0
    assert any("PUTIN" in c.matched_name.upper() for c in candidates)


def test_match_method_tagged_as_vector(searcher):
    normalized = _normalizer.normalize("Sergey Shoygu", "individual")
    candidates = searcher.search(normalized, normal_candidates=[])
    assert all(c.match_method == "vector" for c in candidates)


def test_skips_already_found_by_normal_search(searcher):
    normalized = _normalizer.normalize("Vladimir Putin", "individual")
    from screening_v2.normal_search import NormalSearcher
    normal = NormalSearcher(SessionLocal)
    normal_candidates = normal.search(normalized)
    if not normal_candidates:
        pytest.skip("No normal candidates found for Putin")
    vector_candidates = searcher.search(normalized, normal_candidates=normal_candidates)
    normal_ids = {c.entity_id for c in normal_candidates}
    vector_ids = {c.entity_id for c in vector_candidates}
    assert not (normal_ids & vector_ids)


def test_combined_score_between_zero_and_one(searcher):
    normalized = _normalizer.normalize("Vladimir Putin", "individual")
    candidates = searcher.search(normalized, normal_candidates=[])
    for c in candidates:
        assert 0.0 <= c.match_score <= 1.0
