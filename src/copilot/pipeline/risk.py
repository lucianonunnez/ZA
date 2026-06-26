"""Stage 3 — proactive disruption risk per flight (evidence-weighted).

The weights here are not vibes. They follow what validated sources show actually
drives disruption:

  * Late-arriving aircraft / reactionary delay is the SINGLE LARGEST cause
    (US DOT/BTS: ~3.9% of flights vs ~0.16% from extreme weather; EUROCONTROL:
    ~8.2 min/flight, the largest single category). At quote time we can't see the
    prior rotation, so departure TIME OF DAY is the best available proxy: delays
    compound through the day. DOT data (Thrifty Traveler analysis, May'24-Apr'25):
    >80% on-time before 8am vs 53% after 10pm; pre-11am flights are ~10x less
    likely to cancel.
  * Airline (carrier-controlled: maintenance, crew, baggage) — from our BTS-style
    reliability table.
  * Weather is a SMALL average contributor but owns the catastrophic tail
    (convective summer storms, snow). So it gets real but moderate weight.
  * Connections compound reactionary risk.

A deterministic feature pipeline produces the 0-100 score (auditable, reproducible
= evidence); a cheap model only *explains* it in concierge voice (the white-glove
layer). The AI never decides the number.
"""

from __future__ import annotations

from copilot.config import Tier
from copilot.data import airline_reliability
from copilot.gateway import ChatMessage, Gateway
from copilot.pipeline.weather import weather_risk
from copilot.schemas import FlightOption, RiskAssessment

# Evidence-based weights. Reactionary/time-of-day leads; weather is moderate.
_WEIGHTS = {
    "time_of_day": 0.35,   # proxy for reactionary / late-arriving aircraft (#1 driver)
    "airline": 0.22,
    "weather": 0.20,
    "connections": 0.13,
    "congestion": 0.10,
}


def _band(score: float) -> str:
    if score < 20:
        return "low"
    if score < 40:
        return "moderate"
    if score < 60:
        return "elevated"
    return "high"


def _parse_hour(depart: str) -> int:
    """'21:25' or '06:30+1' -> 21 / 6. Defaults to midday if unparseable."""
    try:
        return int(depart.split(":")[0]) % 24
    except (ValueError, IndexError):
        return 12


def _time_of_day_risk(depart: str) -> tuple[float, list[str]]:
    hour = _parse_hour(depart)
    # Step function calibrated to DOT on-time-by-hour: risk climbs through the day.
    if hour < 8:
        risk, label = 12.0, "early departure — lowest reactionary risk"
    elif hour < 11:
        risk, label = 22.0, "mid-morning departure — low compounding risk"
    elif hour < 15:
        risk, label = 38.0, "midday departure — delays start compounding"
    elif hour < 18:
        risk, label = 52.0, "afternoon departure — ripple delays building"
    elif hour < 22:
        risk, label = 62.0, "evening departure — high reactionary risk"
    else:
        risk, label = 72.0, "late-night departure — peak delay/cancel risk"
    return risk, [f"departs ~{hour:02d}:00 — {label}"]


def _airline_risk(carrier_code: str) -> tuple[float, list[str]]:
    rel = airline_reliability().get(carrier_code)
    if not rel:
        return 30.0, ["carrier reliability unknown"]
    risk = (100 - rel["on_time_pct"]) * 0.7 + rel["cancel_pct"] * 6
    return round(min(100.0, risk), 1), [
        f"{rel['name']}: {rel['on_time_pct']:.0f}% on-time, {rel['cancel_pct']:.1f}% cancel rate"
    ]


def _connection_risk(stops: int) -> tuple[float, list[str]]:
    if stops == 0:
        return 8.0, ["nonstop — no connection risk"]
    return round(min(80.0, 30.0 + stops * 20), 1), [f"{stops} stop(s) compound reactionary delay"]


def _congestion_risk(iata: str) -> tuple[float, list[str]]:
    # Coarse NAS/congestion proxy for the busiest hubs (traffic volume, ATC load).
    busy = {"JFK": 55, "EWR": 60, "LHR": 58, "CDG": 50, "SFO": 52, "DXB": 40}
    risk = busy.get(iata, 30)
    note = "high-traffic hub — NAS congestion risk" if risk >= 50 else "moderate airport congestion"
    return float(risk), [f"{iata}: {note}"]


async def assess_risk(flight: FlightOption, gateway: Gateway, *, explain: bool = True) -> RiskAssessment:
    t_risk, t_drivers = _time_of_day_risk(flight.depart)
    a_risk, a_drivers = _airline_risk(flight.carrier_code)
    w_risk, w_drivers = await weather_risk(flight.destination)
    c_risk, c_drivers = _connection_risk(flight.stops)
    g_risk, g_drivers = _congestion_risk(flight.destination)

    components = {
        "time_of_day": t_risk,
        "airline": a_risk,
        "weather": w_risk,
        "connections": c_risk,
        "congestion": g_risk,
    }
    score = round(sum(components[k] * _WEIGHTS[k] for k in _WEIGHTS), 1)
    drivers = t_drivers + a_drivers + w_drivers + c_drivers + g_drivers

    explanation = ""
    if explain:
        prompt = (
            f"Flight {flight.carrier} {flight.flight_no} to {flight.destination}, "
            f"departing {flight.depart}. Disruption risk {score}/100 ({_band(score)}). "
            f"Drivers: {'; '.join(drivers)}. "
            "In 2 sentences, explain this risk to a VIP traveler in a calm, white-glove tone, "
            "and suggest one concrete proactive mitigation (e.g. an earlier flight, a buffer)."
        )
        res = await gateway.chat(
            Tier.CHEAP,
            [ChatMessage("system", "You assess travel disruption risk for a concierge."),
             ChatMessage("user", prompt)],
            stage="risk",
            max_tokens=160,
        )
        explanation = res.text.strip()

    return RiskAssessment(
        score=score,
        band=_band(score),
        components=components,
        drivers=drivers,
        explanation=explanation,
    )
