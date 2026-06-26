"""Two-layer eval scoring.

Layer 1 — deterministic field checks: did extraction get origin/destination/cabin/
passengers right vs the labeled expectation? Cheap, objective, no model needed.

Layer 2 — LLM-as-judge: a *different* model (JUDGE tier) rates the concierge
recommendation's quality 1-10. Kept separate from the models under test so a model
never grades its own homework.
"""

from __future__ import annotations

import json

from copilot.config import Tier
from copilot.gateway import ChatMessage, Gateway
from copilot.schemas import Recommendation, TripBrief

_JUDGE_SYSTEM = """You are a strict evaluator of a travel concierge's recommendation.
Score it 1-10 on: does it clearly recommend one option, justify it with price/points/
risk, and read like a professional white-glove message? Return ONLY JSON:
{"score": <int 1-10>, "reasoning": "<one sentence>"}."""


def field_accuracy(brief: TripBrief, expect: dict) -> tuple[float, list[str]]:
    """Fraction of expected fields the extraction got right."""
    hits, misses = 0, []
    for key, want in expect.items():
        got = getattr(brief, key, None)
        got_val = got.value if hasattr(got, "value") else got
        if str(got_val).lower() == str(want).lower():
            hits += 1
        else:
            misses.append(f"{key}: got {got_val!r}, expected {want!r}")
    return (hits / len(expect) if expect else 1.0), misses


async def judge_recommendation(rec: Recommendation, gateway: Gateway) -> tuple[int, str]:
    payload = (
        f"Headline: {rec.headline}\nRationale: {rec.rationale}\n"
        f"WhatsApp message: {rec.whatsapp_message}\n"
        f"Recommended index: {rec.recommended_index} of {len(rec.options)} options."
    )
    res = await gateway.chat(
        Tier.JUDGE,
        [ChatMessage("system", _JUDGE_SYSTEM), ChatMessage("user", payload)],
        stage="judge",
        json_mode=True,
        max_tokens=120,
    )
    try:
        text = res.text.strip()
        start, end = text.find("{"), text.rfind("}")
        data = json.loads(text[start : end + 1])
        return int(data.get("score", 0)), data.get("reasoning", "")
    except Exception:
        return 0, "judge output unparseable"
