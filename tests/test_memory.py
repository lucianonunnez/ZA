"""Customer intelligence: the system should learn and improve the next quote."""

import pytest

from copilot.memory import JsonMemoryStore
from copilot.memory.base import MemberProfile, TripOutcome
from copilot.pipeline import run_concierge
from copilot.schemas import Cabin


@pytest.fixture
def store(tmp_path):
    return JsonMemoryStore(path=str(tmp_path / "mem.json"))


def test_learns_preferences_from_trips(store):
    for _ in range(3):
        store.record_trip("vip1", TripOutcome(
            origin="JFK", destination="LHR", carrier_code="BA", cabin=Cabin.business,
            booked_with_points=True, on_time=True,
        ))
    p = store.get("vip1")
    assert p.preferred_cabin == Cabin.business
    assert "BA" in p.preferred_carriers
    assert p.home_airport == "JFK"
    assert "Avios" in p.loyalty_programs
    assert p.trips_count == 3


def test_profile_hint_is_compact_nl(store):
    store.upsert(MemberProfile(handle="v", home_airport="JFK", preferred_cabin=Cabin.business))
    hint = store.get("v").as_hint()
    assert "JFK" in hint and "business" in hint


async def test_second_quote_uses_memory(store):
    # Sparse message that omits origin and cabin.
    msg = "two of us to London, leaving thursday"

    cold = await run_concierge(msg)
    assert cold.member is None
    assert cold.brief.cabin == Cabin.economy  # nothing to lean on

    # Teach the system this member flies JFK business.
    for _ in range(2):
        store.record_trip("vip1", TripOutcome(
            origin="JFK", destination="LHR", carrier_code="BA", cabin=Cabin.business,
        ))

    warm = await run_concierge(msg, member_handle="vip1", store=store)
    assert warm.member is not None
    # The same sparse message now resolves to the member's known cabin + origin.
    assert warm.brief.cabin == Cabin.business
    assert warm.brief.origin == "JFK"
