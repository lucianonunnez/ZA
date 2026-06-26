"""Django ORM models — the member CRM / customer-intelligence store.

Two tables: Member (the learned profile) and TripRecord (the raw history we learn
from). The same preference-learning logic as the offline store is reused, so the
Django and JSON stores stay behaviorally identical.
"""

from __future__ import annotations

from django.db import models


class Member(models.Model):
    CABIN_CHOICES = [
        ("economy", "Economy"), ("premium_economy", "Premium economy"),
        ("business", "Business"), ("first", "First"),
    ]

    handle = models.SlugField(unique=True, help_text="Stable member identifier")
    name = models.CharField(max_length=120, blank=True)
    home_airport = models.CharField(max_length=4, blank=True, null=True)
    preferred_cabin = models.CharField(max_length=20, choices=CABIN_CHOICES, blank=True, null=True)
    preferred_carriers = models.JSONField(default=list, blank=True)
    loyalty_programs = models.JSONField(default=list, blank=True)
    avoid_redeyes = models.BooleanField(default=False)
    trips_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["handle"]

    def __str__(self) -> str:
        return f"{self.name or self.handle} ({self.trips_count} trips)"


class TripRecord(models.Model):
    member = models.ForeignKey(Member, related_name="trips", on_delete=models.CASCADE)
    origin = models.CharField(max_length=4)
    destination = models.CharField(max_length=4)
    carrier_code = models.CharField(max_length=3)
    cabin = models.CharField(max_length=20, choices=Member.CABIN_CHOICES)
    booked_with_points = models.BooleanField(default=False)
    on_time = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.origin}->{self.destination} {self.carrier_code} {self.cabin}"
