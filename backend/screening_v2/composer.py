from __future__ import annotations
from .models import ScreeningResult

_PRIORITY = {"MATCH": 3, "REVIEW": 2, "NO_MATCH": 1}


class VerdictComposer:
    def compose(self, originator: ScreeningResult, beneficiary: ScreeningResult) -> dict:
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