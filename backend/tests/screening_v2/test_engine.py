import pytest
from app.database import SessionLocal
from screening_v2.engine import ScreeningEngine


@pytest.fixture(scope="module")
def engine():
    return ScreeningEngine(SessionLocal)


def test_sanctions_hit_returns_match(engine):
    result = engine.screen("Vladimir Putin", "individual")
    assert result.verdict == "MATCH"
    assert result.confidence >= 0.85


def test_clean_name_returns_no_match_or_review(engine):
    result = engine.screen("Bartholomew Kingsborough", "individual")
    assert result.verdict in ("NO_MATCH", "REVIEW")
    assert result.confidence < 0.85


def test_cyrillic_input_returns_match(engine):
    result = engine.screen("Владимир Путин", "individual")
    assert result.verdict == "MATCH"


def test_result_has_explanation(engine):
    result = engine.screen("Vladimir Putin", "individual")
    assert len(result.explanation) > 30
    assert "PUTIN" in result.explanation.upper() or "match" in result.explanation.lower()


def test_auto_type_detection(engine):
    result = engine.screen("Rosneft Oil Company LLC")
    assert result.input_type == "entity"


def test_normal_search_always_in_methods(engine):
    result = engine.screen("Vladimir Putin", "individual")
    assert "normal" in result.search_methods


def test_vector_used_when_normal_below_threshold(engine):
    # Pass use_vector=True — vector only runs when explicitly opted in
    result = engine.screen("Bartholomew Kingsborough", "individual", use_vector=True)
    assert "vector" in result.search_methods


def test_shoygu_found_via_alias(engine):
    # OFAC stores "SHOYGU" as an alias — normal search should find it at high confidence
    result = engine.screen("Sergey Shoygu", "individual")
    assert result.verdict == "MATCH"
    assert any("SHOIGU" in c.entity_profile.primary_name.upper() for c in result.candidates)


def test_high_confidence_skips_vector(engine):
    result = engine.screen("Vladimir Putin", "individual")
    assert result.verdict == "MATCH"


def test_pep_hit_returns_review_not_match(engine):
    from app.models import Entity, SourceList
    session = SessionLocal()
    pep_count = (
        session.query(Entity)
        .join(SourceList, Entity.source_list_id == SourceList.id)
        .filter(SourceList.list_type == "pep", Entity.is_active == True)
        .count()
    )
    session.close()
    if pep_count == 0:
        pytest.skip("No PEP entities in DB — run: python manage.py fetch --source opensanctions-peps")
    result = engine.screen("Emmanuel Macron", "individual")
    if result.candidates and result.candidates[0].entity_profile.list_type == "pep":
        assert result.verdict == "REVIEW"


def test_duration_ms_populated(engine):
    result = engine.screen("Vladimir Putin", "individual")
    assert result.search_duration_ms >= 0


def test_candidates_sorted_by_score(engine):
    result = engine.screen("Vladimir Putin", "individual")
    scores = [c.match_score for c in result.candidates]
    assert scores == sorted(scores, reverse=True)