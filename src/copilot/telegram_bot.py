"""Telegram bot — the concierge on the channel members actually use.

Ascend's model is concierge-over-chat (WhatsApp); this exposes the exact same
pipeline on Telegram so you can message it from your phone and get a quote with
real disruption risk back. Each Telegram user is treated as a member, so the
customer-intelligence layer personalizes their next quote.

Dependency-light: raw Bot API over httpx long-polling, no extra packages, no
public URL needed (great for Codespaces/local demos).

    export TELEGRAM_BOT_TOKEN=...      # from @BotFather
    export COPILOT_FLIGHT_SOURCE=opensky   # real flights for any route
    python -m copilot.telegram_bot
"""

from __future__ import annotations

import asyncio
import os

import httpx

from copilot.pipeline import run_concierge
from copilot.pipeline.orchestrator import ConciergeResult

_API = "https://api.telegram.org/bot{token}/{method}"

_WELCOME = (
    "<b>Concierge Copilot</b>\n"
    "Tell me a trip in plain language and I'll quote it with a real disruption-risk read.\n\n"
    "e.g. <i>NYC to London next Thursday, business, morning arrival</i>"
)


def format_reply(result: ConciergeResult) -> str:
    """Render a ConciergeResult as a Telegram HTML message. Pure + testable."""
    b, rec, t = result.brief, result.recommendation, result.trace
    lines = [f"<b>{b.origin} → {b.destination}</b> · {b.cabin.value} · {b.passengers} pax"]
    if result.member and result.member.as_hint():
        lines.append(f"<i>known: {result.member.as_hint()}</i>")
    lines.append("")

    if not rec.options:
        if "UNKNOWN" in (b.origin, b.destination):
            return ("I didn't catch a route there. Tell me where from and to — e.g. "
                    "<i>NYC to London business, morning arrival</i>.")
        lines.append(rec.whatsapp_message or "No options found for this route yet.")
    else:
        for i, o in enumerate(rec.options[:4]):
            f, r = o.flight, o.risk
            star = "⭐ " if i == rec.recommended_index else ""
            price = f"${f.cash_price_usd:,.0f}" + (" est." if f.estimated else "")
            save = f" · save {f.savings_pct:.0f}%" if f.savings_pct else ""
            lines.append(f"{star}<b>{f.carrier} {f.flight_no}</b> {f.depart} · {price}{save}"
                         f" · risk {r.score:.0f} ({r.band})")
        if rec.whatsapp_message:
            lines.append("")
            lines.append(rec.whatsapp_message)

    lines.append("")
    models = ", ".join(sorted(t.get("by_model", {}))) or "—"
    lines.append(f"<i>models {models} · cost ${t['total_cost_usd']:.4f}</i>")
    return "\n".join(lines)


class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self._offset = 0

    def _url(self, method: str) -> str:
        return _API.format(token=self.token, method=method)

    async def _send(self, client: httpx.AsyncClient, chat_id: int, text: str) -> None:
        await client.post(self._url("sendMessage"),
                          json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

    async def _handle(self, client: httpx.AsyncClient, message: dict) -> None:
        chat_id = message["chat"]["id"]
        text = (message.get("text") or "").strip()
        if not text:
            return
        if text.startswith("/start"):
            await self._send(client, chat_id, _WELCOME)
            return
        # Each Telegram user is a member, so memory personalizes their next quote.
        handle = f"tg:{message['from']['id']}"
        await self._send(client, chat_id, "Sourcing options…")
        try:
            result = await run_concierge(text, member_handle=handle)
            await self._send(client, chat_id, format_reply(result))
        except Exception as exc:  # noqa: BLE001 — never let one message kill the bot
            await self._send(client, chat_id, f"Sorry, something went wrong: {exc}")

    async def run(self) -> None:
        async with httpx.AsyncClient(timeout=40.0) as client:
            print("Concierge Telegram bot is running. Press Ctrl+C to stop.")
            while True:
                try:
                    resp = await client.get(
                        self._url("getUpdates"),
                        params={"offset": self._offset, "timeout": 30},
                    )
                    updates = resp.json().get("result", [])
                except Exception:
                    await asyncio.sleep(3)
                    continue
                for upd in updates:
                    self._offset = upd["update_id"] + 1
                    msg = upd.get("message") or upd.get("edited_message")
                    if msg:
                        await self._handle(client, msg)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN (get one from @BotFather on Telegram).")
    asyncio.run(TelegramBot(token).run())


if __name__ == "__main__":
    main()
