from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()


def _build_prompt(tx: dict) -> str:
    la = tx["layer_a"]
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

    return (
        f"Transaction under review:\n"
        f"- Label: {tx['label']}\n"
        f"- Originator: {tx['originator']}\n"
        f"- Beneficiary: {tx['beneficiary']}\n"
        f"- Amount: {tx['amount']:,.2f} {tx['currency']}\n"
        f"- Counterparty country: {tx['counterparty_country']}\n"
        f"- Confidence: {tx['confidence'] * 100:.0f}%\n"
        f"- Triggered layers: {', '.join(tx['triggered_layers']) or 'none'}\n\n"
        f"Layer A — Sanctions screening:\n"
        f"  Originator verdict: {orig['verdict']}{orig_match}\n"
        f"  Beneficiary verdict: {bene['verdict']}{bene_match}\n\n"
        f"Layer B — Behavioral AML:\n"
        f"  Score: {lb['score']} → {lb['outcome']}\n"
        f"  Rules fired:\n{rules_text}\n\n"
        f"System explanation: {tx['explanation']}\n\n"
        f'Respond with JSON only: {{"verdict": "BLOCK"|"RELEASE"|"ESCALATE", "reasoning": "<1-3 sentence rationale>"}}'
    )


async def get_ai_suggestion(tx: dict) -> dict:
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a compliance AI assistant helping a human analyst review "
                    "flagged payment transactions. Based on the AML screening data, "
                    "suggest the most appropriate verdict: BLOCK (high risk, prevent payment), "
                    "RELEASE (low risk, allow payment), or ESCALATE (uncertain, needs senior review). "
                    "Be concise and evidence-based."
                ),
            },
            {"role": "user", "content": _build_prompt(tx)},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)
