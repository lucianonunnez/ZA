"""Stage 4 — strong model turns scored options into a concierge recommendation.

Deterministic ranking (cheapest-effective + lowest risk) decides the *what*; the
strong model writes the *how it sounds* — a paste-ready WhatsApp message in the
white-glove voice. Same separation as risk: facts are computed, prose is generated.
"""

from __future__ import annotations

import json

from copilot.config import Tier
from copilot.gateway import ChatMessage, Gateway
from copilot.schemas import Recommendation, ScoredOption, TripBrief

_SYSTEM = """You are a premium travel concierge writing to a VIP member on WhatsApp.
Tone: warm, concise, confident, never salesy. You are given ranked, scored flight
options (with disruption risk and points savings already computed — trust them).
Return ONLY JSON with keys:
  headline (string, one line),
  rationale (2-3 sentences explaining the pick: balance price, points savings, risk),
  whatsapp_message (the paste-ready message to the member, friendly, <90 words),
  caveats (list of short strings — anything to confirm or watch).
Do not invent prices, times, or savings; use only what is provided."""


def _rank(options: list[ScoredOption]) -> int:
    """Pick the best: reward points savings, penalize disruption risk and cash."""
    def score(o: ScoredOption) -> float:
        savings = o.flight.savings_pct or 0
        return savings - o.risk.score * 0.6 - o.flight.cash_price_usd / 200
    best = max(range(len(options)), key=lambda i: score(options[i]))
    return best


def _options_payload(options: list[ScoredOption]) -> str:
    rows = []
    for i, o in enumerate(options):
        rows.append(
            {
                "index": i,
                "carrier": o.flight.carrier,
                "flight_no": o.flight.flight_no,
                "depart": o.flight.depart,
                "arrive": o.flight.arrive,
                "stops": o.flight.stops,
                "cash_usd": o.flight.cash_price_usd,
                "points": o.flight.points_price,
                "points_program": o.flight.points_program,
                "points_savings_pct": o.flight.savings_pct,
                "risk_score": o.risk.score,
                "risk_band": o.risk.band,
            }
        )
    return json.dumps(rows, indent=2)


async def recommend(
    brief: TripBrief, options: list[ScoredOption], gateway: Gateway
) -> Recommendation:
    if not options:
        return Recommendation(
            headline="No matching options found",
            options=[],
            recommended_index=-1,
            rationale="I couldn't find inventory for this route in our system yet.",
            whatsapp_message=(
                "Thanks! I'm sourcing options for this route now and will follow up shortly "
                "with the best business-class routings and any points sweet spots."
            ),
            caveats=brief.missing_or_assumed,
        )

    best = _rank(options)
    payload = (
        f"Member request: {brief.origin} -> {brief.destination}, {brief.cabin.value}, "
        f"{brief.passengers} pax. Preferences: {', '.join(brief.preferences) or 'none stated'}.\n"
        f"Pre-ranked options (index {best} is our recommended pick):\n{_options_payload(options)}"
    )
    res = await gateway.chat(
        Tier.STRONG,
        [ChatMessage("system", _SYSTEM), ChatMessage("user", payload)],
        stage="recommend",
        max_tokens=500,
        json_mode=True,
    )

    try:
        text = res.text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1].removeprefix("json").strip()
        start, end = text.find("{"), text.rfind("}")
        data = json.loads(text[start : end + 1])
    except Exception:
        data = {}

    return Recommendation(
        headline=data.get("headline", f"Recommended: {options[best].flight.carrier}"),
        options=options,
        recommended_index=best,
        rationale=data.get("rationale", ""),
        whatsapp_message=data.get("whatsapp_message", ""),
        caveats=data.get("caveats", []) + brief.missing_or_assumed,
    )
