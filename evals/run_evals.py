"""Multi-model scorecard.

Runs the dataset through the pipeline once per candidate model (used as the CHEAP
extraction model), measuring extraction accuracy, judge score, cost and latency.
The output table is the "evidence over vibes" artifact: which model to trust for
which job, with numbers — exactly the standard-setting a lead engineer owns.

    python evals/run_evals.py                 # default model set
    python evals/run_evals.py glm-4.5-air gpt-4o-mini deepseek-v3

With no API key the gateway uses the mock provider, so this still runs offline
(numbers are illustrative but the harness is real).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Allow running as a plain script: add src/ to path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from copilot.config import MODELS, Tier  # noqa: E402
from copilot.gateway import Gateway  # noqa: E402
from copilot.pipeline.extract import extract_brief  # noqa: E402
from copilot.pipeline.flights import search_flights  # noqa: E402
from copilot.pipeline.recommend import recommend  # noqa: E402
from copilot.pipeline.risk import assess_risk  # noqa: E402
from copilot.schemas import ScoredOption  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from judge import field_accuracy, judge_recommendation  # noqa: E402

DEFAULT_MODELS = ["glm-4.5-air", "deepseek-v3", "gpt-4o-mini", "claude-haiku", "mock"]


def load_dataset() -> list[dict]:
    path = Path(__file__).resolve().parent / "dataset.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


async def eval_model(model: str, dataset: list[dict]) -> dict:
    gw = Gateway()
    acc_total, judge_total = 0.0, 0

    for row in dataset:
        # Force this candidate as the CHEAP-tier extraction model.
        brief = await extract_brief(row["message"], _PinnedCheap(gw, model))
        acc, _ = field_accuracy(brief, row["expect"])
        acc_total += acc

        flights = search_flights(brief)
        risks = await asyncio.gather(*(assess_risk(f, gw, explain=False) for f in flights))
        scored = [ScoredOption(flight=f, risk=r) for f, r in zip(flights, risks, strict=True)]
        rec = await recommend(brief, scored, gw)
        score, _ = await judge_recommendation(rec, gw)
        judge_total += score

    n = len(dataset)
    return {
        "model": model,
        "field_accuracy": round(100 * acc_total / n, 1),
        "judge_avg": round(judge_total / n, 1),
        "cost_usd": gw.ledger.total_cost,
        "latency_ms": round(gw.ledger.total_latency_ms / n, 1),
    }


class _PinnedCheap:
    """Wrap a Gateway so CHEAP-tier calls go to a pinned model (for benchmarking)."""

    def __init__(self, gw: Gateway, model: str):
        self._gw = gw
        self._model = model
        self.ledger = gw.ledger

    async def chat(self, tier, messages, **kw):
        if tier == Tier.CHEAP:
            kw["model"] = self._model
        return await self._gw.chat(tier, messages, **kw)


async def main(models: list[str]) -> None:
    dataset = load_dataset()
    console = Console()
    console.print(f"[bold]Scorecard[/bold] · {len(dataset)} cases · CHEAP-tier model swap\n")

    rows = []
    for m in models:
        if m not in MODELS:
            console.print(f"[yellow]skip unknown model: {m}[/yellow]")
            continue
        rows.append(await eval_model(m, dataset))

    rows.sort(key=lambda r: (-r["field_accuracy"], r["cost_usd"]))
    table = Table(title="Model scorecard (extraction tier)")
    table.add_column("Model", style="cyan")
    table.add_column("Field acc %", justify="right")
    table.add_column("Judge /10", justify="right")
    table.add_column("Cost $", justify="right")
    table.add_column("Latency ms/case", justify="right")
    for r in rows:
        table.add_row(
            r["model"], f"{r['field_accuracy']}", f"{r['judge_avg']}",
            f"{r['cost_usd']:.4f}", f"{r['latency_ms']}",
        )
    console.print(table)
    console.print(
        "\n[dim]Note: with no API key this runs on the mock provider, so numbers are "
        "illustrative. Add OPENROUTER_API_KEY + COPILOT_PROVIDER=openrouter for real ones.[/dim]"
    )

    # When running in GitHub Actions, render the scorecard into the run summary —
    # the "arena" leaderboard, visible right in the workflow page.
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        lines = [
            "## 🏟️ Model scorecard (extraction tier)",
            "",
            "| Model | Field acc % | Judge /10 | Cost $ | Latency ms/case |",
            "|---|--:|--:|--:|--:|",
        ]
        for r in rows:
            lines.append(
                f"| `{r['model']}` | {r['field_accuracy']} | {r['judge_avg']} | "
                f"{r['cost_usd']:.4f} | {r['latency_ms']} |"
            )
        with open(summary, "a") as fh:
            fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    chosen = sys.argv[1:] or DEFAULT_MODELS
    asyncio.run(main(chosen))
