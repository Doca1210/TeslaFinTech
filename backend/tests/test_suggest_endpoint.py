"""Integration tests for the /transactions/{tx_id}/suggest endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app

MINIMAL_TX = {
    "id": 5,
    "label": "Test wire",
    "originator": "Alice",
    "beneficiary": "Bob LLC",
    "amount": 10000.0,
    "currency": "USD",
    "counterparty_country": "DE",
    "confidence": 0.75,
    "triggered_layers": ["layer_b_behavioral"],
    "explanation": "Behavioral flag only.",
    "layer_a": {
        "originator": {"verdict": "NO_MATCH", "confidence": 0.4, "matched_name": None, "matched_entity_id": None},
        "beneficiary": {"verdict": "NO_MATCH", "confidence": 0.4, "matched_name": None, "matched_entity_id": None},
    },
    "layer_b": {"score": 30, "outcome": "review", "rules_fired": [{"rule_id": "amt_large", "severity": "medium", "score": 30, "reason": "Large amount"}]},
    "ownership_risk": None,
}


@pytest.fixture(autouse=True)
def set_tx_cache(monkeypatch):
    monkeypatch.setattr(main_module, "_transactions_cache", [MINIMAL_TX])


def test_suggest_endpoint_returns_suggestion():
    with patch("app.main.get_ai_suggestion", new=AsyncMock(return_value={"verdict": "ESCALATE", "reasoning": "Behavioral flag only, no sanctions hit."})):
        client = TestClient(app)
        response = client.post("/transactions/5/suggest")

    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "ESCALATE"
    assert data["reasoning"] == "Behavioral flag only, no sanctions hit."


def test_suggest_endpoint_404_for_unknown_id():
    client = TestClient(app)
    response = client.post("/transactions/999/suggest")
    assert response.status_code == 404


def test_suggest_endpoint_502_when_openai_fails():
    with patch("app.main.get_ai_suggestion", new=AsyncMock(side_effect=RuntimeError("OpenAI down"))):
        client = TestClient(app)
        response = client.post("/transactions/5/suggest")

    assert response.status_code == 502
    assert response.json()["detail"] == "AI suggestion unavailable"
