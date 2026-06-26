"""DjangoMemoryStore — the production member store, ORM-backed.

Implements the exact same `MemoryStore` protocol as the offline JSON store, and
reuses the shared `apply_outcome` learning logic, so swapping persistence changes
nothing about behavior. This is dependency inversion paying off: the pipeline
never knows whether it's talking to JSON or Postgres.
"""

from __future__ import annotations

from copilot.memory.base import MemberProfile, TripOutcome
from copilot.memory.learn import apply_outcome
from copilot.schemas import Cabin
from members.models import Member, TripRecord


def _to_profile(m: Member) -> MemberProfile:
    return MemberProfile(
        handle=m.handle,
        name=m.name,
        home_airport=m.home_airport,
        preferred_cabin=Cabin(m.preferred_cabin) if m.preferred_cabin else None,
        preferred_carriers=m.preferred_carriers or [],
        loyalty_programs=m.loyalty_programs or [],
        avoid_redeyes=m.avoid_redeyes,
        trips_count=m.trips_count,
    )


def _save_profile(m: Member, p: MemberProfile) -> None:
    m.name = p.name
    m.home_airport = p.home_airport
    m.preferred_cabin = p.preferred_cabin.value if p.preferred_cabin else None
    m.preferred_carriers = p.preferred_carriers
    m.loyalty_programs = p.loyalty_programs
    m.avoid_redeyes = p.avoid_redeyes
    m.trips_count = p.trips_count
    m.save()


class DjangoMemoryStore:
    """Postgres/SQLite-backed member store (same interface as JsonMemoryStore)."""

    def get(self, handle: str) -> MemberProfile | None:
        m = Member.objects.filter(handle=handle).first()
        return _to_profile(m) if m else None

    def upsert(self, profile: MemberProfile) -> MemberProfile:
        m, _ = Member.objects.get_or_create(handle=profile.handle)
        _save_profile(m, profile)
        return profile

    def record_trip(self, handle: str, outcome: TripOutcome) -> MemberProfile:
        m, _ = Member.objects.get_or_create(handle=handle)
        history = [
            TripOutcome(
                origin=t.origin, destination=t.destination, carrier_code=t.carrier_code,
                cabin=Cabin(t.cabin), booked_with_points=t.booked_with_points, on_time=t.on_time,
            )
            for t in m.trips.all()
        ]
        updated = apply_outcome(_to_profile(m), outcome, history)
        TripRecord.objects.create(
            member=m, origin=outcome.origin, destination=outcome.destination,
            carrier_code=outcome.carrier_code, cabin=outcome.cabin.value,
            booked_with_points=outcome.booked_with_points, on_time=outcome.on_time,
        )
        _save_profile(m, updated)
        return updated
