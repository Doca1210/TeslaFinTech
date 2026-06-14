from __future__ import annotations

import json
import os
import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_SYSTEM_PROMPT = (
    "You are a compliance AI assistant helping a human analyst review "
    "flagged payment transactions. Based on the AML screening data, "
    "suggest the most appropriate verdict: BLOCK (high risk, prevent payment), "
    "RELEASE (low risk, allow payment), or ESCALATE (uncertain, needs senior review). "
    "Be concise and evidence-based. "
    'Respond with JSON only: {"verdict": "BLOCK"|"RELEASE"|"ESCALATE", "reasoning": "<1-3 sentence rationale>"}'
)

_VALID_VERDICTS = {"BLOCK", "RELEASE", "ESCALATE"}


def _build_prompt(tx: dict) -> str:
    for key in ("layer_a", "layer_b", "triggered_layers"):
        if key not in tx:
            raise KeyError(f"Transaction dict is missing required key: '{key}'")

    la = tx["layer_a"]

    for key in ("originator", "beneficiary"):
        if key not in la:
            raise KeyError(f"layer_a is missing required key: '{key}'")

    lb = tx["layer_b"]
    orig = la["originator"]
    bene = la["beneficiary"]

    orig_match = (
        f" → matched: {orig['matched_name']} [{orig['matched_entity_id']}]"
        if orig.get("matched_name")
        else ""
    )
    bene_match = (
        f" → matched: {bene['matched_name']} [{bene['matched_entity_id']}]"
        if bene.get("matched_name")
        else ""
    )

    rules = lb.get("rules_fired", [])
    rules_text = (
        "\n".join(
            f"  - {r['rule_id']} (severity={r['severity']}, score={r['score']}): {r['reason']}"
            for r in rules
        )
        or "  None"
    )

    triggered = tx.get("triggered_layers") or []

    return (
        f"Transaction under review:\n"
        f"- Label: {tx['label']}\n"
        f"- Originator: {tx['originator']}\n"
        f"- Beneficiary: {tx['beneficiary']}\n"
        f"- Amount: {tx['amount']:,.2f} {tx['currency']}\n"
        f"- Counterparty country: {tx['counterparty_country']}\n"
        f"- Confidence: {tx['confidence'] * 100:.0f}%\n"
        f"- Triggered layers: {', '.join(triggered) or 'none'}\n\n"
        f"Layer A — Sanctions screening:\n"
        f"  Originator verdict: {orig['verdict']}{orig_match}\n"
        f"  Beneficiary verdict: {bene['verdict']}{bene_match}\n\n"
        f"Layer B — Behavioral AML:\n"
        f"  Score: {lb['score']} → {lb['outcome']}\n"
        f"  Rules fired:\n{rules_text}\n\n"
        f"System explanation: {tx['explanation']}\n"
    )


async def get_ai_suggestion(tx: dict) -> dict:
    response = await _client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_prompt(tx)}],
    )

    # Extract text block (adaptive thinking may prepend thinking blocks)
    text = next(
        (block.text for block in response.content if block.type == "text"),
        None,
    )
    if text is None:
        raise ValueError("Claude returned no text content in response")

    # Parse JSON, with fallback extraction in case of surrounding prose
    try:
        result = json.loads(text.strip())
    except json.JSONDecodeError:
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if not match:
            raise ValueError(f"Could not parse JSON from Claude response: {text[:200]}")
        result = json.loads(match.group())

    if "verdict" not in result or "reasoning" not in result:
        raise ValueError(
            f"Claude response missing required keys ('verdict', 'reasoning'). Got: {list(result.keys())}"
        )
    if result["verdict"] not in _VALID_VERDICTS:
        raise ValueError(
            f"Claude returned invalid verdict '{result['verdict']}'. "
            f"Expected one of: {sorted(_VALID_VERDICTS)}"
        )

    return result
