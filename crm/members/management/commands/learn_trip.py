"""`python manage.py learn_trip <handle> JFK LHR BA business` — teach the CRM.

A thin management command so the concierge team can record outcomes from the
shell; the same DjangoMemoryStore the API uses.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from copilot.memory.base import TripOutcome
from copilot.schemas import Cabin
from members.store import DjangoMemoryStore


class Command(BaseCommand):
    help = "Record a completed trip for a member and update learned preferences."

    def add_arguments(self, parser) -> None:
        parser.add_argument("handle")
        parser.add_argument("origin")
        parser.add_argument("destination")
        parser.add_argument("carrier_code")
        parser.add_argument("cabin", choices=[c.value for c in Cabin])
        parser.add_argument("--points", action="store_true")

    def handle(self, *args, **opts) -> None:
        try:
            profile = DjangoMemoryStore().record_trip(
                opts["handle"],
                TripOutcome(
                    origin=opts["origin"], destination=opts["destination"],
                    carrier_code=opts["carrier_code"], cabin=Cabin(opts["cabin"]),
                    booked_with_points=opts["points"],
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"{opts['handle']}: {profile.as_hint()} ({profile.trips_count} trips)"
        ))
