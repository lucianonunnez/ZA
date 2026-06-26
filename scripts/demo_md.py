"""Run one concierge quote and emit Markdown — for the GitHub Actions UI.

Writes to $GITHUB_STEP_SUMMARY when present (so the result renders right in the
workflow run page) and also prints to stdout. Inputs come from env so the
workflow can pass them: DEMO_REQUEST, DEMO_MEMBER.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copilot.config import settings  # noqa: E402
from copilot.pipeline import run_concierge  # noqa: E402


def to_markdown(result) -> str:
    b, rec, t = result.brief, result.recommendation, result.trace
    out = [
        f"## Concierge quote — {b.origin} → {b.destination}",
        f"**Cabin:** {b.cabin.value} · **Pax:** {b.passengers}"
        + ("  ·  _budget flexible_" if b.budget_flexible else ""),
    ]
    if result.member and result.member.as_hint():
        out.append(f"> 🧠 Member intelligence applied: {result.member.as_hint()}")
    out += [
        "",
        "| | Flight | Depart | Cash $ | Points save | Disruption risk |",
        "|---|---|---|--:|--:|---|",
    ]
    for i, o in enumerate(rec.options):
        f, r = o.flight, o.risk
        star = "⭐" if i == rec.recommended_index else ""
        out.append(
            f"| {star} | {f.carrier} {f.flight_no} | {f.depart} | "
            f"{f.cash_price_usd:,.0f} | {f.savings_pct or 0:.0f}% | {r.score:.0f} ({r.band}) |"
        )
    if rec.whatsapp_message:
        out += ["", "**📱 Paste-ready message**", "", f"> {rec.whatsapp_message}"]
    out += [
        "",
        f"<sub>provider=`{settings.resolve_provider()}` · "
        f"models={', '.join(sorted(t['by_model']))} · calls={t['calls']} · "
        f"cost=${t['total_cost_usd']:.4f} · fallbacks={t['fallbacks']}</sub>",
    ]
    return "\n".join(out)


async def main() -> None:
    request = os.getenv("DEMO_REQUEST") or (
        sys.argv[1] if len(sys.argv) > 1
        else "I need NYC to London next Thursday, business, morning arrival, flexible budget"
    )
    member = os.getenv("DEMO_MEMBER") or None
    result = await run_concierge(request, member_handle=member or None)
    md = to_markdown(result)

    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(md + "\n")
    print(md)


if __name__ == "__main__":
    asyncio.run(main())
