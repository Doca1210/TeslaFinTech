from __future__ import annotations
from .models import ScreeningResult

_PRIORITY = {"MATCH": 3, "REVIEW": 2, "NO_MATCH": 1}

# Maps aml_detect outcome strings → unified verdict contribution
_BEHAVIORAL_VERDICT = {
    "block_and_review": "MATCH",
    "decline": "MATCH",
    "review": "REVIEW",
    "approve": "NO_MATCH",
}


class VerdictComposer:
    def compose(self, originator: ScreeningResult, beneficiary: ScreeningResult) -> dict:
        """Layer A only: compose two-party sanctions screening results."""
        verdict = max(
            originator.verdict, beneficiary.verdict, key=lambda v: _PRIORITY[v]
        )
        confidence = max(originator.confidence, beneficiary.confidence)
        explanation = self._build_explanation(originator, beneficiary)
        return {
            "verdict": verdict,
            "confidence": confidence,
            "parties": {"originator": originator, "beneficiary": beneficiary},
            "explanation": explanation,
        }

    def compose_payment(
        self,
        originator: ScreeningResult,
        beneficiary: ScreeningResult,
        behavioral_score: float,
        behavioral_outcome: str,
        behavioral_hits: list,
        ownership: dict | None = None,
    ) -> dict:
        """Full pipeline: Layer A (sanctions) + Layer B (behavioral AML) + Layer C (ownership).

        behavioral_outcome is the string returned by aml_detect._outcome():
        'approve' | 'review' | 'decline' | 'block_and_review'.
        behavioral_hits is the list[RuleHit] from aml_detect.evaluate().
        ownership is the optional Layer-C dict from
        ``app.ownership.OwnershipRiskEngine.assess()`` (verdict/score/paths). When
        omitted, the verdict is unchanged from the A+B pipeline.
        """
        layer_a = self.compose(originator, beneficiary)
        layer_b_verdict = _BEHAVIORAL_VERDICT.get(behavioral_outcome, "NO_MATCH")
        layer_c_verdict = ownership["verdict"] if ownership else "NO_MATCH"
        ownership_score = ownership["score"] if ownership else 0.0

        verdict = max(
            layer_a["verdict"], layer_b_verdict, layer_c_verdict,
            key=lambda v: _PRIORITY[v],
        )
        confidence = max(
            layer_a["confidence"],
            min(behavioral_score / 100.0, 1.0),
            min(ownership_score / 100.0, 1.0),
        )

        triggered_layers: list[str] = []
        if layer_a["verdict"] != "NO_MATCH":
            triggered_layers.append("layer_a_sanctions")
        if layer_b_verdict != "NO_MATCH":
            triggered_layers.append("layer_b_behavioral")
        if layer_c_verdict != "NO_MATCH":
            triggered_layers.append("layer_c_ownership")

        explanation = self._build_payment_explanation(
            layer_a, behavioral_outcome, behavioral_score, behavioral_hits, verdict, ownership
        )

        return {
            "verdict": verdict,
            "confidence": round(confidence, 4),
            "recommended_action": _verdict_to_action(verdict),
            "parties": layer_a["parties"],
            "behavioral_score": behavioral_score,
            "behavioral_outcome": behavioral_outcome,
            "behavioral_rule_ids": [h.rule_id for h in behavioral_hits],
            "ownership_risk": ownership,
            "triggered_layers": triggered_layers,
            "explanation": explanation,
        }

    @staticmethod
    def _build_explanation(orig: ScreeningResult, bene: ScreeningResult) -> str:
        parts = []
        if orig.verdict == "NO_MATCH":
            parts.append(f"Originator '{orig.input_raw}': clean.")
        else:
            parts.append(f"Originator flagged — {orig.explanation}")
        if bene.verdict == "NO_MATCH":
            parts.append(f"Beneficiary '{bene.input_raw}': clean.")
        else:
            parts.append(f"Beneficiary flagged — {bene.explanation}")
        return " ".join(parts)

    @staticmethod
    def _build_payment_explanation(
        layer_a: dict,
        behavioral_outcome: str,
        behavioral_score: float,
        behavioral_hits: list,
        final_verdict: str,
        ownership: dict | None = None,
    ) -> str:
        parts = [f"Final verdict: {final_verdict}."]
        parts.append(f"Layer A (sanctions): {layer_a['explanation']}")
        rule_ids = ", ".join(h.rule_id for h in behavioral_hits) if behavioral_hits else "none"
        parts.append(
            f"Layer B (behavioral): outcome={behavioral_outcome}, "
            f"score={behavioral_score:.0f}, rules fired=[{rule_ids}]."
        )
        if ownership:
            parts.append(
                f"Layer C (ownership): verdict={ownership['verdict']}, "
                f"score={ownership['score']:.0f}. {ownership['reason']}"
            )
        return " ".join(parts)


def _verdict_to_action(verdict: str) -> str:
    return {"MATCH": "BLOCK", "REVIEW": "MANUAL_REVIEW", "NO_MATCH": "PASS"}[verdict]