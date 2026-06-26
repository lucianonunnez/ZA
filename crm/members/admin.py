"""Admin = the concierge team's member CRM, for free (the Django payoff)."""

from django.contrib import admin

from members.models import Member, TripRecord


class TripInline(admin.TabularInline):
    model = TripRecord
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("handle", "name", "home_airport", "preferred_cabin", "trips_count", "updated_at")
    search_fields = ("handle", "name")
    list_filter = ("preferred_cabin", "avoid_redeyes")
    inlines = [TripInline]


@admin.register(TripRecord)
class TripRecordAdmin(admin.ModelAdmin):
    list_display = ("member", "origin", "destination", "carrier_code", "cabin", "on_time", "created_at")
    list_filter = ("cabin", "on_time", "carrier_code")
