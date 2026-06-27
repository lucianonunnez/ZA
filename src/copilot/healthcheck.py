"""Connection health checks — verify the live integrations actually work.

Evidence over vibes: instead of finding out at demo time that the Telegram token
or the model key is dead (e.g. a token was regenerated but the secret wasn't
updated), run this and see OK/FAIL per connection. A scheduled GitHub Action runs
it so a broken connection emails you — it doesn't surprise you.

    copilot doctor              # local, pretty table
    python -m copilot.healthcheck   # CI: writes a summary, exits non-zero on fail
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import httpx

from copilot.config import settings


@dataclass
class Check:
    name: str
    required: bool
    ok: bool
    detail: str


async def check_telegram(client: httpx.AsyncClient, token: str) -> Check:
    if not token:
        return Check("Telegram", True, False, "TELEGRAM_BOT_TOKEN not set")
    try:
        r = await client.get(f"https://api.telegram.org/bot{token}/getMe")
        d = r.json()
        if d.get("ok"):
            return Check("Telegram", True, True, f"@{d['result'].get('username', '?')} reachable")
        return Check("Telegram", True, False, d.get("description", "token rejected"))
    except Exception as exc:  # noqa: BLE001
        return Check("Telegram", True, False, str(exc)[:80])


async def check_openrouter(client: httpx.AsyncClient, key: str) -> Check:
    if not key:
        return Check("OpenRouter", False, False, "OPENROUTER_API_KEY not set (mock provider ok)")
    try:
        r = await client.get("https://openrouter.ai/api/v1/key",
                             headers={"Authorization": f"Bearer {key}"})
        if r.status_code == 200:
            data = r.json().get("data", {})
            limit = data.get("limit")
            return Check("OpenRouter", False, True,
                         f"key valid{f', limit ${limit}' if limit is not None else ''}")
        return Check("OpenRouter", False, False, f"HTTP {r.status_code} — key rejected")
    except Exception as exc:  # noqa: BLE001
        return Check("OpenRouter", False, False, str(exc)[:80])


async def run_checks() -> list[Check]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        return list(await asyncio.gather(
            check_telegram(client, os.getenv("TELEGRAM_BOT_TOKEN", "")),
            check_openrouter(client, settings.openrouter_key),
        ))


def _summary(checks: list[Check]) -> str:
    lines = ["| Connection | Status | Detail |", "|---|---|---|"]
    for c in checks:
        icon = "✅" if c.ok else ("❌" if c.required else "⚠️")
        lines.append(f"| {c.name} | {icon} | {c.detail} |")
    return "\n".join(lines)


def main() -> None:
    checks = asyncio.run(run_checks())
    for c in checks:
        icon = "OK " if c.ok else ("FAIL" if c.required else "warn")
        print(f"[{icon}] {c.name}: {c.detail}")

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as fh:
            fh.write("## 🩺 Connection health\n\n" + _summary(checks) + "\n")

    # Fail the process only if a *required* connection is down.
    if any(c.required and not c.ok for c in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
