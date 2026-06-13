"""Tests for VerdictComposer.compose_payment() — Layer A + Layer B integration."""
from dataclasses import dataclass

import pytest
from screening_v2.composer import VerdictComposer
from screening_v2.models import ScreeningResult


def _sr(verdict: str, confidence: float, name: str = "Test") -> ScreeningResult:
    return ScreeningResult(
        verdict=verdict,
        confidence=confidence,
        input_raw=name,
        input_type="individual",
        input_normalized=name.lower(),
        search_methods=["normal"],
        search_duration_ms=5,
        candidates=[],
        explanation="stub",
    )


@dataclass
class _Hit:
    rule_id: str


CLEAN_A = _sr("NO_MATCH", 0.0, "Alice Clean")
CLEAN_B = _sr("NO_MATCH", 0.0, "Bob Clean")
MATCH_A = _sr("MATCH", 0.95, "Bad Actor")
REVIEW_A = _sr("REVIEW", 0.72, "Risky Name")


# ---------------------------------------------------------------------------
# Verdict priority
# ---------------------------------------------------------------------------

def test_all_clean_returns_no_match():
    r = VerdictComposer().compose_payment(CLEAN_A, CLEAN_B, 0.0, "approve", [])
    assert r["verdict"] == "NO_MATCH"
    assert r["recommended_action"] == "PASS"


def test_layer_a_match_beats_behavioral_approve():
    r = VerdictComposer().compose_payment(MATCH_A, CLEAN_B, 0.0, "approve", [])
    assert r["verdict"] == "MATCH"
    assert r["recommended_action"] == "BLOCK"


def test_behavioral_block_beats_clean_sanctions():
    hits = [_Hit("structuring_7d"), _Hit("velocity_24h")]
    r = VerdictComposer().compose_payment(CLEAN_A, CLEAN_B, 95.0, "block_and_review", hits)
    assert r["verdict"] == "MATCH"
    assert r["recommended_action"] == "BLOCK"


def test_behavioral_decline_maps_to_match():
    r = VerdictComposer().compose_payment(CLEAN_A, CLEAN_B, 65.0, "decline", [_Hit("amt_large")])
    assert r["verdict"] == "MATCH"


def test_behavioral_review_maps_to_review():
    r = VerdictComposer().compose_payment(CLEAN_A, CLEAN_B, 35.0, "review", [_Hit("amt_large")])
    assert r["verdict"] == "REVIEW"
    assert r["recommended_action"] == "MANUAL_REVIEW"


def test_layer_a_review_plus_behavioral_approve_gives_review():
    r = VerdictComposer().compose_payment(REVIEW_A, CLEAN_B, 0.0, "approve", [])
    assert r["verdict"] == "REVIEW"


def test_match_beats_review_across_layers():
    hits = [_Hit("velocity_24h")]
    r = VerdictComposer().compose_payment(MATCH_A, CLEAN_B, 35.0, "review", hits)
    assert r["verdict"] == "MATCH"


# ---------------------------------------------------------------------------
# Triggered layers
# ---------------------------------------------------------------------------

def test_triggered_layers_empty_when_all_clean():
    r = VerdictComposer().compose_payment(CLEAN_A, CLEAN_B, 0.0, "approve", [])
    assert r["triggered_layers"] == []


def test_triggered_layers_layer_a_only():
    r = VerdictComposer().compose_payment(MATCH_A, CLEAN_B, 0.0, "approve", [])
    assert "layer_a_sanctions" in r["triggered_layers"]
    assert "layer_b_behavioral" not in r["triggered_layers"]


def test_triggered_layers_layer_b_only():
    r = VerdictComposer().compose_payment(CLEAN_A, CLEAN_B, 40.0, "review", [_Hit("amt_large")])
    assert "layer_b_behavioral" in r["triggered_layers"]
    assert "layer_a_sanctions" not in r["triggered_layers"]


def test_triggered_layers_both():
    r = VerdictComposer().compose_payment(MATCH_A, CLEAN_B, 65.0, "decline", [_Hit("geo_high_risk")])
    assert set(r["triggered_layers"]) == {"layer_a_sanctions", "layer_b_behavioral"}


# ---------------------------------------------------------------------------
# Payload structure
# ---------------------------------------------------------------------------

def test_behavioral_rule_ids_populated():
    hits = [_Hit("amt_large"), _Hit("geo_high_risk")]
    r = VerdictComposer().compose_payment(CLEAN_A, CLEAN_B, 65.0, "decline", hits)
    assert r["behavioral_rule_ids"] == ["amt_large", "geo_high_risk"]


def test_parties_dict_present():
    r = VerdictComposer().compose_payment(MATCH_A, CLEAN_B, 0.0, "approve", [])
    assert r["parties"]["originator"] is MATCH_A
    assert r["parties"]["beneficiary"] is CLEAN_B


def test_confidence_uses_behavioral_score_when_higher():
    r = VerdictComposer().compose_payment(CLEAN_A, CLEAN_B, 100.0, "block_and_review", [])
    assert r["confidence"] == 1.0


def test_confidence_uses_screening_score_when_higher():
    r = VerdictComposer().compose_payment(MATCH_A, CLEAN_B, 0.0, "approve", [])
    assert r["confidence"] == pytest.approx(0.95)


def test_explanation_contains_verdict():
    r = VerdictComposer().compose_payment(MATCH_A, CLEAN_B, 0.0, "approve", [])
    assert "MATCH" in r["explanation"]


def test_explanation_contains_behavioral_outcome():
    r = VerdictComposer().compose_payment(CLEAN_A, CLEAN_B, 35.0, "review", [_Hit("amt_large")])
    assert "review" in r["explanation"]
