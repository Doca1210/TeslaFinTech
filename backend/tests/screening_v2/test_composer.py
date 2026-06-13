from screening_v2.composer import VerdictComposer
from screening_v2.models import ScreeningResult


def _result(verdict: str, confidence: float, name: str = "Test") -> ScreeningResult:
    return ScreeningResult(
        verdict=verdict,
        confidence=confidence,
        input_raw=name,
        input_type="individual",
        input_normalized=name.lower(),
        search_methods=["normal"],
        search_duration_ms=10,
        candidates=[],
        explanation="test explanation",
    )


def test_match_beats_review():
    c = VerdictComposer()
    result = c.compose(_result("MATCH", 0.92, "Bad Actor"), _result("REVIEW", 0.71, "Risky Corp"))
    assert result["verdict"] == "MATCH"


def test_match_beats_no_match():
    c = VerdictComposer()
    result = c.compose(_result("MATCH", 0.92, "Bad Actor"), _result("NO_MATCH", 0.0, "Clean Co"))
    assert result["verdict"] == "MATCH"


def test_review_beats_no_match():
    c = VerdictComposer()
    result = c.compose(_result("NO_MATCH", 0.0, "Clean"), _result("REVIEW", 0.71, "Risky"))
    assert result["verdict"] == "REVIEW"


def test_both_no_match_returns_no_match():
    c = VerdictComposer()
    result = c.compose(_result("NO_MATCH", 0.0, "A"), _result("NO_MATCH", 0.0, "B"))
    assert result["verdict"] == "NO_MATCH"


def test_confidence_is_max_of_both():
    c = VerdictComposer()
    result = c.compose(_result("MATCH", 0.92, "A"), _result("REVIEW", 0.71, "B"))
    assert result["confidence"] == 0.92


def test_parties_dict_has_both():
    c = VerdictComposer()
    orig = _result("MATCH", 0.92, "Bad Actor")
    bene = _result("NO_MATCH", 0.0, "Clean Co")
    result = c.compose(orig, bene)
    assert result["parties"]["originator"] is orig
    assert result["parties"]["beneficiary"] is bene


def test_explanation_mentions_clean_party():
    c = VerdictComposer()
    result = c.compose(_result("MATCH", 0.92, "Bad Actor"), _result("NO_MATCH", 0.0, "Clean Co"))
    assert "Clean Co" in result["explanation"] or "clean" in result["explanation"].lower()


def test_explanation_mentions_flagged_party():
    c = VerdictComposer()
    result = c.compose(_result("MATCH", 0.92, "Bad Actor"), _result("NO_MATCH", 0.0, "Clean Co"))
    assert "Bad Actor" in result["explanation"] or "flagged" in result["explanation"].lower()