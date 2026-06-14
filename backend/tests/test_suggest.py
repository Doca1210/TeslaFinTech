"""Tests for the AI suggestion module."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch


SAMPLE_TX = {
    "id": 7,
    "label": "High-risk wire to Iran",
    "originator": "Alice Johnson",
    "beneficiary": "Caspian Oil Trading",
    "amount": 95000.0,
    "currency": "USD",
    "counterparty_country": "IR",
    "confidence": 0.88,
    "triggered_layers": ["layer_a_sanctions", "layer_b_behavioral"],
    "explanation": "Sanctions screening: Beneficiary matched OFAC SDN. Behavioral analysis: high-risk jurisdiction.",
    "layer_a": {
        "originator": {"verdict": "NO_MATCH", "confidence": 0.5, "matched_name": None, "matched_entity_id": None},
        "beneficiary": {"verdict": "MATCH", "confidence": 0.88, "matched_name": "Caspian Energy LLC", "matched_entity_id": "OFAC_SDN:9921"},
    },
    "layer_b": {
        "score": 55,
        "outcome": "review",
        "rules_fired": [
            {"rule_id": "geo_high_risk", "severity": "high", "score": 35, "reason": "Counterparty country IR is high-risk"},
            {"rule_id": "amt_large", "severity": "medium", "score": 20, "reason": "Amount 95000 exceeds threshold"},
        ],
    },
    "ownership_risk": None,
}


def _mock_openai_response(content: str) -> MagicMock:
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    return mock_response


def test_get_ai_suggestion_returns_verdict_and_reasoning():
    from app.suggest import get_ai_suggestion

    async def run():
        with patch("app.suggest.AsyncOpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(
                return_value=_mock_openai_response(
                    '{"verdict": "BLOCK", "reasoning": "Beneficiary matched OFAC SDN list with high confidence."}'
                )
            )
            return await get_ai_suggestion(SAMPLE_TX)

    result = asyncio.run(run())
    assert result["verdict"] == "BLOCK"
    assert result["reasoning"] == "Beneficiary matched OFAC SDN list with high confidence."


def test_get_ai_suggestion_propagates_openai_exception():
    from app.suggest import get_ai_suggestion

    async def run():
        with patch("app.suggest.AsyncOpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API error"))
            return await get_ai_suggestion(SAMPLE_TX)

    try:
        asyncio.run(run())
        assert False, "Should have raised"
    except RuntimeError as e:
        assert "API error" in str(e)
