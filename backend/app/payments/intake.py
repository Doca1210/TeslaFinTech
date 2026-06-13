"""Payment Intake: validate and normalize incoming payment instructions.

Corresponds to the "Payment Intake" box in docs/design/priority_backlog.md section 2.3.
This is the single entry point for /screen — every screening layer receives the
PaymentInstruction produced here, never the raw request body.

TODO (T-001): implement validation/normalization, including the backward-compatible
adapter for the legacy `{counterparty_name}` Transaction shape.
"""

from __future__ import annotations

from typing import Any

from app.payments.schemas import PaymentInstruction


class PaymentIntake:
    """Validates and normalizes raw payment payloads into PaymentInstruction."""

    def normalize(self, raw_payload: dict[str, Any]) -> PaymentInstruction:
        """Validate `raw_payload` and return a normalized PaymentInstruction.

        Should also populate `countries_in_scope` from originator/beneficiary/bank
        countries and preserve the original payload in `raw_payload`.
        """
        raise NotImplementedError
