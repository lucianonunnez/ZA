"""Django ORM store test — proves the production member store works and matches.

Configures Django with a throwaway SQLite DB, migrates, and exercises the same
MemoryStore contract the JSON store satisfies. Runs inside the normal pytest run.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="module")
def django_store(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "crm.sqlite3"
    os.environ["DJANGO_SETTINGS_MODULE"] = "crm.settings"
    os.environ["DATABASE_URL"] = f"sqlite:///{db}"

    import django

    django.setup()
    from django.core.management import call_command

    call_command("migrate", verbosity=0, run_syncdb=True)

    from members.store import DjangoMemoryStore

    return DjangoMemoryStore()


def test_django_store_learns_like_json(django_store):
    from copilot.memory.base import TripOutcome
    from copilot.schemas import Cabin

    for _ in range(3):
        django_store.record_trip("vip-orm", TripOutcome(
            origin="JFK", destination="LHR", carrier_code="BA",
            cabin=Cabin.business, booked_with_points=True,
        ))
    p = django_store.get("vip-orm")
    assert p.preferred_cabin == Cabin.business
    assert p.home_airport == "JFK"
    assert "Avios" in p.loyalty_programs
    assert p.trips_count == 3
