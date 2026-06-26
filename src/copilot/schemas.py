"""Typed contracts for the whole pipeline.

Every stage boundary is a Pydantic model. That's the "decompose ambiguous work
into specs" discipline: a model can't quietly hand the next stage garbage —
validation fails loud, which is exactly the agent failure mode we want to catch.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class Cabin(str, Enum):
    economy = "economy"
    premium_economy = "premium_economy"
    business = "business"
    first = "first"


class TripBrief(BaseModel):
    """Structured intent extracted from a free-text traveler message."""

    origin: str = Field(description="IATA code or city of departure")
    destination: str = Field(description="IATA code or city of arrival")
    depart_date: date | None = None
    return_date: date | None = None
    cabin: Cabin = Cabin.economy
    passengers: int = 1
    preferences: list[str] = Field(default_factory=list)
    budget_flexible: bool = False
    notes: str = ""
    # Honesty signal: what the model was unsure about. Surfacing this is the
    # opposite of hallucinating confidence — the concierge knows what to confirm.
    missing_or_assumed: list[str] = Field(default_factory=list)


class FlightOption(BaseModel):
    carrier: str
    carrier_code: str
    flight_no: str
    origin: str
    destination: str
    depart: str
    arrive: str
    cabin: Cabin
    duration_min: int
    stops: int
    cash_price_usd: float
    # Points/miles arbitrage — Zach's personal obsession baked into the data.
    points_price: int | None = None
    points_program: str | None = None
    points_cash_value_usd: float | None = None  # what those points are "worth"

    @property
    def savings_pct(self) -> float | None:
        """How much cheaper booking with points is vs cash, as a %."""
        if self.points_cash_value_usd and self.cash_price_usd:
            return round(100 * (1 - self.points_cash_value_usd / self.cash_price_usd), 1)
        return None


class RiskAssessment(BaseModel):
    """Proactive disruption risk for one flight option.

    This is an explainable *risk index*, not a probability prediction. We weight
    the drivers that validated sources (US DOT/BTS, EUROCONTROL) show actually
    move disruption, with the biggest, most actionable lever — departure time of
    day / reactionary delay — on top. We deliberately do NOT claim a % cancel
    probability, because the rich historical features that real predictive models
    need aren't available at quote time. Honesty over a false precision.
    """

    score: float = Field(ge=0, le=100, description="0 = calm, 100 = high disruption risk")
    band: str  # low | moderate | elevated | high
    # Component sub-scores (0-100), keyed by driver name. Auditable breakdown.
    components: dict[str, float] = Field(default_factory=dict)
    drivers: list[str] = Field(default_factory=list)   # human-readable reasons
    explanation: str = ""                               # LLM-written, concierge voice


class InboundStatus(BaseModel):
    """The feeder leg: the previous flight of the same aircraft (the #1 driver)."""

    aircraft_reg: str | None = None
    inbound_flight_no: str | None = None
    inbound_from: str | None = None
    airborne: bool = False
    inbound_delay_min: int = 0       # >0 means the feeder is already running late
    source: str = "unknown"          # opensky | mock | unavailable


class FlightStatus(BaseModel):
    """Live status for a specific booked flight (number + date)."""

    flight_no: str
    status: str = "unknown"          # scheduled|active|landed|delayed|cancelled|unknown
    scheduled_departure: str | None = None
    estimated_departure: str | None = None
    departure_delay_min: int = 0
    aircraft_reg: str | None = None
    inbound: InboundStatus | None = None
    source: str = "unknown"          # aerodatabox | aviationstack | mock | unavailable

    @property
    def on_time_confidence(self) -> float:
        """0-100. How confident we are it leaves roughly on time, from live signals."""
        if self.status == "cancelled":
            return 0.0
        delay = max(self.departure_delay_min, self.inbound.inbound_delay_min if self.inbound else 0)
        # Each ~15 min of observed delay knocks down confidence.
        return round(max(0.0, 100.0 - delay * 3.0), 1)


class ScoredOption(BaseModel):
    flight: FlightOption
    risk: RiskAssessment


class ProactiveAlert(BaseModel):
    """Post-purchase monitoring output: should we proactively warn the member?"""

    flight_no: str
    level: str                       # clear | watch | warning | critical
    should_notify: bool
    on_time_confidence: float
    reasons: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    member_message: str = ""         # paste-ready proactive WhatsApp, concierge voice


class Recommendation(BaseModel):
    """Final concierge-ready output."""

    headline: str
    options: list[ScoredOption]
    recommended_index: int
    rationale: str
    whatsapp_message: str   # paste-ready, white-glove tone
    caveats: list[str] = Field(default_factory=list)
