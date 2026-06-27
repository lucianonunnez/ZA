"""Smoke-test agent — runs the real pipeline on a schedule, inside GitHub.

Uses your model key (GLM via OpenRouter) to run real quotes end to end and verify
they produce a recommendation. Scheduled in CI, so if the live system ever breaks
(key expired, model/provider change, pipeline regression) the job fails and GitHub
tells you — the agents verify themselves. Evidence over vibes.

    python scripts/smoke.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copilot.config import settings  # noqa: E402
from copilot.pipeline import run_concierge  # noqa: E402

ROUTES = [
    "NYC to London business class, morning arrival",
    "Buenos Aires to Miami business",
]


async def main() -> None:
    out = [
        f"## 🤖 Smoke test · provider `{settings.resolve_provider()}`",
        "",
        "| Route | Pick | Options | Risk | Cost |",
        "|---|---|--:|--:|--:|",
    ]
    failures = 0
    for route in ROUTES:
        res = await run_concierge(route, explain_risk=False)
        rec = res.recommendation
        ok = bool(rec.options) and rec.recommended_index >= 0
        failures += 0 if ok else 1
        if rec.options:
            pick = rec.options[rec.recommended_index]
            carrier, risk = pick.flight.carrier, f"{pick.risk.score:.0f}"
        else:
            carrier, risk = "—", "—"
        out.append(f"| {route[:34]} | {carrier} | {len(rec.options)} | {risk} | "
                   f"${res.trace['total_cost_usd']:.4f} |")
        print(("OK  " if ok else "FAIL") + f" {route} -> {len(rec.options)} options, "
              f"models={sorted(res.trace.get('by_model', {}))}")

    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write("\n".join(out) + "\n")

    if failures:
        raise SystemExit(f"{failures} route(s) returned no recommendation")


if __name__ == "__main__":
    asyncio.run(main())
