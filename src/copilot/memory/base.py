"""Memory contracts. Two stores implement this: JSON (offline) and Django (prod)."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from copilot.schemas import Cabin


class TripOutcome(BaseModel):
    """One completed trip — the raw signal we learn preferences from."""

    origin: str
    destination: str
    carrier_code: str
    cabin: Cabin
    booked_with_points: bool = False
    on_time: bool = True


class MemberProfile(BaseModel):
    """What we know about a member. Injected into extraction + recommendation."""

    handle: str
    name: str = ""
    home_airport: str | None = None
    preferred_cabin: Cabin | None = None
    preferred_carriers: list[str] = Field(default_factory=list)
    loyalty_programs: list[str] = Field(default_factory=list)
    avoid_redeyes: bool = False
    trips_count: int = 0

    def as_hint(self) -> str:
        """A compact natural-language hint to prime the extraction model."""
        bits = []
        if self.home_airport:
            bits.append(f"usually departs from {self.home_airport}")
        if self.preferred_cabin:
            bits.append(f"prefers {self.preferred_cabin.value}")
        if self.preferred_carriers:
            bits.append(f"likes {', '.join(self.preferred_carriers)}")
        if self.loyalty_programs:
            bits.append(f"collects {', '.join(self.loyalty_programs)}")
        if self.avoid_redeyes:
            bits.append("avoids red-eye departures")
        return "; ".join(bits)


class MemoryStore(Protocol):
    """Minimal persistence surface. Implemented by JSON and Django stores."""

    def get(self, handle: str) -> MemberProfile | None: ...

    def upsert(self, profile: MemberProfile) -> MemberProfile: ...

    def record_trip(self, handle: str, outcome: TripOutcome) -> MemberProfile: ...
