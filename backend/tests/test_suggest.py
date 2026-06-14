"""Tests for the AI suggestion module."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(
                '{"verdict": "BLOCK", "reasoning": "Beneficiary matched OFAC SDN list with high confidence."}'
            )
        )
        with patch("app.suggest._client", mock_client):
            result = await get_ai_suggestion(SAMPLE_TX)
        return result, mock_client

    result, mock_client = asyncio.run(run())
    assert result["verdict"] == "BLOCK"
    assert result["reasoning"] == "Beneficiary matched OFAC SDN list with high confidence."

    # Fix 5: Assert that the prompt sent to the model contains key transaction data.
    call_args = mock_client.chat.completions.create.call_args
    messages = call_args.kwargs.get("messages") or call_args.args[0] if call_args.args else call_args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "Caspian Oil Trading" in user_content
    assert "geo_high_risk" in user_content


def test_get_ai_suggestion_propagates_openai_exception():
    from app.suggest import get_ai_suggestion

    # Fix 6: Use pytest.raises instead of bare assert False.
    async def run():
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API error"))
        with patch("app.suggest._client", mock_client):
            return await get_ai_suggestion(SAMPLE_TX)

    with pytest.raises(RuntimeError, match="API error"):
        asyncio.run(run())
