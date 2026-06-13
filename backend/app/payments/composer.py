"""Verdict Composer — merges per-layer results into one ScreeningDecision.

Corresponds to the "Verdict Composer" box in docs/design/priority_backlog.md
section 2.3. Rule: any layer MATCH -> MATCH; else any layer REVIEW -> REVIEW;
else NO_MATCH (section 2.2, T-002).
"""

from __future__ import annotations

from app.payments.schemas import LayerResult, PaymentInstruction, ScreeningDecision


class VerdictComposer:
    """Combines LayerResults from all registered layers into one decision."""

    def compose(
        self,
        payment: PaymentInstruction,
        layer_results: list[LayerResult],
    ) -> ScreeningDecision:
        """Apply MATCH > REVIEW > NO_MATCH precedence and build the explanation.

        TODO (T-002/T-009): pick the overall verdict and confidence, populate
        `list_versions` and `engine_version`, and build a structured 2-4 sentence
        explanation covering which layers ran and what triggered the verdict.
        """
        raise NotImplementedError
