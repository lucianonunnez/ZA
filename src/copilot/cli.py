"""Demo CLI. The thing you actually run live in the interview.

    copilot quote "I need NYC to London thursday, business, morning arrival"
    copilot models          # show the registry + which provider is active
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from copilot.config import MODELS, TIER_DEFAULTS, settings
from copilot.gateway import Gateway
from copilot.pipeline import run_concierge

app = typer.Typer(add_completion=False, help="Ascend Concierge Copilot")
console = Console()


@app.command()
def quote(request: str, member: str = typer.Option(None, help="Member handle for customer intelligence")) -> None:
    """Turn a free-text traveler request into a concierge recommendation."""
    result = asyncio.run(run_concierge(request, member_handle=member))
    brief, rec, trace = result.brief, result.recommendation, result.trace
    if result.member and (hint := result.member.as_hint()):
        console.print(f"[dim]Member intelligence applied: {hint}[/dim]")

    console.print(Panel.fit(
        f"[bold]{brief.origin} → {brief.destination}[/bold]  ·  {brief.cabin.value}  ·  "
        f"{brief.passengers} pax" + ("  ·  budget flexible" if brief.budget_flexible else ""),
        title="Trip brief", border_style="cyan",
    ))
    if brief.missing_or_assumed:
        console.print(f"[yellow]To confirm:[/yellow] {', '.join(brief.missing_or_assumed)}\n")

    table = Table(title="Options (ranked)")
    table.add_column("", width=3)
    table.add_column("Flight"); table.add_column("Depart"); table.add_column("Cash $", justify="right")
    table.add_column("Points save", justify="right"); table.add_column("Risk", justify="right")
    for i, o in enumerate(rec.options):
        f, r = o.flight, o.risk
        mark = "[green]★[/green]" if i == rec.recommended_index else ""
        band_color = {"low": "green", "moderate": "yellow", "elevated": "dark_orange", "high": "red"}.get(r.band, "white")
        table.add_row(
            mark, f"{f.carrier} {f.flight_no}", f.depart, f"{f.cash_price_usd:,.0f}",
            f"{f.savings_pct or 0:.0f}%", f"[{band_color}]{r.score:.0f} {r.band}[/{band_color}]",
        )
    console.print(table)

    if rec.recommended_index >= 0:
        pick = rec.options[rec.recommended_index]
        console.print(Panel(rec.whatsapp_message or rec.rationale,
                            title=f"📱 Paste-ready · {pick.flight.carrier}", border_style="green"))
        if pick.risk.explanation:
            console.print(f"[dim]Risk note: {pick.risk.explanation}[/dim]\n")

    console.print(
        f"[dim]provider={settings.resolve_provider()}  ·  models={', '.join(sorted(trace['by_model']))}  "
        f"·  calls={trace['calls']}  ·  cost=${trace['total_cost_usd']:.4f}  "
        f"·  fallbacks={trace['fallbacks']}[/dim]"
    )


@app.command()
def watch(flight_no: str, date: str = typer.Option(None, help="YYYY-MM-DD (optional)")) -> None:
    """Live status for a booked flight: tracks the inbound aircraft (#1 delay driver).

    Upgrades the static risk index into a live, free ADS-B signal once a member has
    a specific flight. With no AERODATABOX_API_KEY it shows a deterministic demo.
    """
    from copilot.pipeline.live import live_flight_status, live_risk_override

    status = asyncio.run(live_flight_status(flight_no, date))
    color = {"scheduled": "green", "active": "green", "landed": "green",
             "delayed": "dark_orange", "cancelled": "red"}.get(status.status, "white")
    lines = [
        f"Status: [{color}]{status.status.upper()}[/{color}]   (source: {status.source})",
        f"Scheduled: {status.scheduled_departure}   Estimated: {status.estimated_departure}",
        f"Departure delay: {status.departure_delay_min} min",
        f"On-time confidence: [bold]{status.on_time_confidence:.0f}%[/bold]",
    ]
    if status.inbound:
        ib = status.inbound
        lines.append(
            f"\n[bold]Inbound aircraft[/bold] {ib.aircraft_reg or '?'} — feeder "
            f"{ib.inbound_flight_no or '?'} from {ib.inbound_from or '?'}: "
            + (f"[dark_orange]~{ib.inbound_delay_min} min late[/dark_orange]"
               if ib.inbound_delay_min else "[green]on time[/green]")
            + f"  (source: {ib.source})"
        )
    override = live_risk_override(status)
    if override:
        lines.append(f"\n[bold]Live risk override:[/bold] {override[0]:.0f}/100 — {'; '.join(override[1])}")
    console.print(Panel("\n".join(lines), title=f"✈ Live watch · {flight_no}", border_style=color))


@app.command()
def monitor(
    flight_no: str,
    to: str = typer.Option("LHR", help="Destination IATA, for weather risk"),
    date: str = typer.Option(None, help="YYYY-MM-DD (optional)"),
) -> None:
    """Post-purchase proactive watch: fuses live delay + weather into an alert.

    The member already booked. This decides whether to proactively reach out, and
    drafts the concierge message. The Ascend 'proactive disruption handling' loop.
    """
    from copilot.pipeline.monitor import monitor_booking

    alert = asyncio.run(monitor_booking(flight_no, to, date))
    color = {"clear": "green", "watch": "yellow", "warning": "dark_orange", "critical": "red"}.get(alert.level, "white")
    body = [
        f"Alert level: [{color}]{alert.level.upper()}[/{color}]   "
        f"(notify member: {'YES' if alert.should_notify else 'no'})",
        f"On-time confidence: [bold]{alert.on_time_confidence:.0f}%[/bold]",
        "\n[bold]Why:[/bold]",
        *[f"  • {r}" for r in alert.reasons],
    ]
    if alert.recommended_action:
        body.append(f"\n[bold]Recommended action:[/bold] {alert.recommended_action}")
    console.print(Panel("\n".join(body), title=f"🛰  Proactive monitor · {flight_no} → {to}", border_style=color))
    if alert.member_message:
        console.print(Panel(alert.member_message, title="📱 Proactive message to member", border_style=color))


@app.command()
def member(
    handle: str,
    learn_trip: str = typer.Option(None, "--learn", help="Record a trip: ORIGIN,DEST,CARRIER,CABIN e.g. JFK,LHR,BA,business"),
) -> None:
    """Show or teach a member profile (the customer-intelligence store)."""
    from copilot.memory import default_store
    from copilot.memory.base import TripOutcome
    from copilot.schemas import Cabin

    store = default_store()
    if learn_trip:
        o, d, c, cab = (x.strip() for x in learn_trip.split(","))
        prof = store.record_trip(handle, TripOutcome(
            origin=o, destination=d, carrier_code=c, cabin=Cabin(cab)))
        console.print(f"[green]Learned.[/green] {handle} now: [bold]{prof.as_hint()}[/bold]  ({prof.trips_count} trips)")
        return

    prof = store.get(handle)
    if not prof:
        console.print(f"[yellow]No profile for '{handle}'.[/yellow] Teach it with --learn JFK,LHR,BA,business")
        return
    console.print(Panel(
        f"Name: {prof.name or handle}\nTrips: {prof.trips_count}\n"
        f"Home: {prof.home_airport}\nCabin: {prof.preferred_cabin.value if prof.preferred_cabin else '—'}\n"
        f"Carriers: {', '.join(prof.preferred_carriers) or '—'}\n"
        f"Loyalty: {', '.join(prof.loyalty_programs) or '—'}",
        title=f"👤 Member · {handle}", border_style="cyan"))


@app.command()
def models() -> None:
    """Show the model registry, tier defaults, and the active provider."""
    console.print(f"Active provider: [bold]{settings.resolve_provider()}[/bold]  "
                  f"(budget cap ${settings.budget_usd:.2f})\n")
    table = Table(title="Model registry")
    table.add_column("Name", style="cyan"); table.add_column("Slug")
    table.add_column("$/1M in", justify="right"); table.add_column("$/1M out", justify="right")
    table.add_column("Tier role")
    role = {v: k.value for k, v in TIER_DEFAULTS.items()}
    for name, spec in MODELS.items():
        table.add_row(name, spec.slug, f"{spec.input_per_1m:.2f}", f"{spec.output_per_1m:.2f}",
                      role.get(name, ""))
    console.print(table)


if __name__ == "__main__":
    app()
