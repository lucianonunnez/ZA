"""Post-purchase proactive monitoring — the heart of the concierge model.

The member has already booked. Now the system *watches* the flight and decides,
proactively, whether to reach out. It fuses everything we discussed:

  * live flight status + inbound-aircraft delay  (live.py — the #1 driver, observed)
  * weather risk at the destination              (weather.py)

into a single alert level, and a cheap model writes the heads-up in concierge
voice with a concrete recommended action. This is "smart angle, not brute force":
we only ping the member when there's something worth saying.
"""

from __future__ import annotations

from copilot.config import Tier
from copilot.gateway import ChatMessage, Gateway
from copilot.pipeline.live import live_flight_status, live_risk_override
from copilot.pipeline.weather import weather_risk
from copilot.schemas import ProactiveAlert


def _level(live_score: float, weather: float) -> tuple[str, bool]:
    worst = max(live_score, weather * 0.6)  # weather weighted below a live delay
    if worst >= 75:
        return "critical", True
    if worst >= 45:
        return "warning", True
    if worst >= 25:
        return "watch", True
    return "clear", False


async def monitor_booking(
    flight_no: str,
    destination: str,
    date: str | None = None,
    gateway: Gateway | None = None,
) -> ProactiveAlert:
    gw = gateway or Gateway()

    status = await live_flight_status(flight_no, date)
    override = live_risk_override(status)
    live_score, live_reasons = override if override else (15.0, ["no live signal yet"])
    w_risk, w_drivers = await weather_risk(destination)

    level, notify = _level(live_score, w_risk)
    reasons = live_reasons + [f"destination weather: {'; '.join(w_drivers)}"]

    action = ""
    message = ""
    if notify:
        delayed = status.departure_delay_min > 0 or (
            status.inbound and status.inbound.inbound_delay_min > 0
        )
        action = (
            "Offer to rebook onto an earlier flight and pre-arrange ground transport buffer."
            if delayed
            else "Monitor closely; pre-stage a backup option in case conditions worsen."
        )
        prompt = (
            f"A VIP member is booked on flight {flight_no} to {destination}. "
            f"Status: {status.status}, departure delay {status.departure_delay_min} min. "
            f"Signals: {'; '.join(reasons)}. Alert level: {level}. "
            f"Write a short, calm, proactive WhatsApp message (<70 words) that warns them "
            f"early, shows we're already handling it, and offers this action: {action}"
        )
        res = await gw.chat(
            Tier.CHEAP,
            [ChatMessage("system", "You are a proactive premium travel concierge for a vip member."),
             ChatMessage("user", prompt)],
            stage="monitor",
            max_tokens=160,
        )
        message = res.text.strip()

    return ProactiveAlert(
        flight_no=flight_no,
        level=level,
        should_notify=notify,
        on_time_confidence=status.on_time_confidence,
        reasons=reasons,
        recommended_action=action,
        member_message=message,
    )
