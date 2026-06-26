"""Preference-learning logic, shared by every MemoryStore implementation.

Kept storage-agnostic so the JSON store and the Django store learn identically —
the only difference between them is *where* the profile is persisted, never *how*
preferences are derived. Single source of truth for the intelligence.
"""

from __future__ import annotations

from collections import Counter

from copilot.memory.base import MemberProfile, TripOutcome

# A carrier_code -> loyalty program mapping (would live in reference data in prod).
_PROGRAMS = {
    "BA": "Avios", "AA": "AAdvantage", "DL": "SkyMiles", "UA": "MileagePlus",
    "VS": "Flying Club", "AF": "Flying Blue", "EK": "Skywards", "SQ": "KrisFlyer",
}


def apply_outcome(profile: MemberProfile, outcome: TripOutcome, history: list[TripOutcome]) -> MemberProfile:
    """Return a profile updated with what this trip (plus history) reveals.

    Deterministic: preferences are the mode of observed behavior, not a guess.
    """
    all_trips = history + [outcome]

    # Most-flown cabin and carriers become the learned preference.
    cabin_mode = Counter(t.cabin for t in all_trips).most_common(1)[0][0]
    carriers = [c for c, _ in Counter(t.carrier_code for t in all_trips).most_common(3)]
    home = Counter(t.origin for t in all_trips).most_common(1)[0][0]

    programs = sorted({_PROGRAMS[t.carrier_code] for t in all_trips if t.carrier_code in _PROGRAMS})

    return profile.model_copy(
        update={
            "preferred_cabin": cabin_mode,
            "preferred_carriers": carriers,
            "home_airport": home,
            "loyalty_programs": programs,
            "trips_count": len(all_trips),
        }
    )
