"""URLconf — the admin panel is the concierge team's member CRM."""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("", admin.site.urls),
]
