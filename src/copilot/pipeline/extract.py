"""Stage 1 — messy free text -> validated TripBrief, using a cheap model.

This is the "decompose ambiguous work into specs" step. We force JSON, validate
with Pydantic, and if the model emits garbage we don't crash the request — we
surface what was missing so the human concierge confirms it. That's the
anti-hallucination posture Zach probes for.
"""

from __future__ import annotations

import json

from copilot.config import Tier
from copilot.gateway import ChatMessage, Gateway
from copilot.guardrails.pii import redact
from copilot.schemas import TripBrief

_SYSTEM = """You extract a structured TripBrief from a traveler's free-text message.
Return ONLY a JSON object with these keys:
  origin (IATA or city), destination (IATA or city), depart_date (YYYY-MM-DD or null),
  return_date (YYYY-MM-DD or null), cabin (economy|premium_economy|business|first),
  passengers (int), preferences (list of strings), budget_flexible (bool),
  notes (string), missing_or_assumed (list of strings describing anything you guessed
  or could not determine — be honest here, do not invent specifics).
Do not wrap the JSON in markdown."""


def _coerce_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1].removeprefix("json").strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


async def extract_brief(message: str, gateway: Gateway) -> TripBrief:
    # PII never reaches the model in the clear — redact before prompting.
    safe = redact(message)
    result = await gateway.chat(
        Tier.CHEAP,
        [ChatMessage("system", _SYSTEM), ChatMessage("user", safe)],
        stage="extract",
        json_mode=True,
        temperature=0.0,
    )
    try:
        data = _coerce_json(result.text)
        return TripBrief.model_validate(data)
    except Exception:
        # Verification caught a bad model output: degrade safely instead of lying.
        return TripBrief(
            origin="UNKNOWN",
            destination="UNKNOWN",
            missing_or_assumed=["could not parse request — needs human review"],
            notes=safe[:280],
        )
