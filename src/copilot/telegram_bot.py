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
    "Send me a trip in plain language and I'll quote it with a real disruption-risk read.\n\n"
    "<b>Try:</b> <i>NYC to London next Thursday, business, morning arrival</i>\n"
    "Reply <b>why</b> any time to see how I score the risk."
)

# A short, truthful explanation of the risk method (the "why").
_RISK_BLURB = (
    "<b>How I score disruption risk</b>\n"
    "It's transparent math on official data, weighted by real impact:\n"
    "• Late-arriving aircraft &amp; departure time — the #1 driver (US DOT)\n"
    "• Airline on-time reliability (US DOT/BTS)\n"
    "• Destination weather (Open-Meteo)\n"
    "• Connections &amp; airport congestion\n"
    "Once a flight is booked, I also track the <b>inbound aircraft live</b> via ADS-B.\n"
    "<i>The AI explains the score — it does not guess it.</i>"
)

_BAND_DOT = {"low": "🟢", "moderate": "🟡", "elevated": "🟠", "high": "🔴"}


def is_risk_question(text: str) -> bool:
    """True for messages that ask how/why the risk works (so we explain it)."""
    t = text.strip().lower().rstrip("?")
    if t in ("why", "por que", "porque", "porqué", "how", "explain"):
        return True
    return any(k in t for k in (
        "how do you score", "how is the risk", "what is the risk", "explain the risk",
        "how risky", "why that risk", "how do you calculate", "riesgo",
    ))


def format_reply(result: ConciergeResult) -> str:
    """Render a ConciergeResult as a Telegram HTML message. Pure + testable."""
    b, rec, t = result.brief, result.recommendation, result.trace

    # No options = no clear route / unsupported city. Give a clear, helpful nudge
    # rather than a vague "sourcing options" — covers typos and replies like "yes".
    if not rec.options:
        return ("I didn't catch a clear route. Send it city to city — e.g. "
                "<i>NYC to London business, morning arrival</i>.")

    header = f"<b>{b.origin} → {b.destination}</b>  ·  {b.cabin.value}  ·  {b.passengers} pax"
    lines = [header]
    if result.member and result.member.as_hint():
        lines.append(f"<i>🧠 known: {result.member.as_hint()}</i>")
    lines.append("")

    for i, o in enumerate(rec.options[:4]):
        f, r = o.flight, o.risk
        dot = _BAND_DOT.get(r.band, "")
        price = f"${f.cash_price_usd:,.0f}" + (" est." if f.estimated else "")
        save = f" · save {f.savings_pct:.0f}%" if f.savings_pct else ""
        title = (f"⭐ <b>{f.carrier} {f.flight_no}</b>" if i == rec.recommended_index
                 else f"{f.carrier} {f.flight_no}")
        lines.append(title)
        lines.append(f"   {f.depart} · {price}{save} · {dot} risk {r.score:.0f}")
    if rec.whatsapp_message:
        lines.append("")
        lines.append(f"💬 {rec.whatsapp_message}")

    lines.append("")
    models = ", ".join(sorted(t.get("by_model", {}))) or "—"
    lines.append(f"<i>models {models} · cost ${t['total_cost_usd']:.4f}</i>")
    lines.append("<i>Reply “why” to see how I score the risk.</i>")
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
        # Short, truthful answer when someone asks how the risk works.
        if is_risk_question(text):
            await self._send(client, chat_id, _RISK_BLURB)
            return
        # Each Telegram user is a member, so memory personalizes their next quote.
        handle = f"tg:{message['from']['id']}"
        await self._send(client, chat_id, "Sourcing options…")
        try:
            # explain_risk=False keeps chat replies fast (no per-flight prose call).
            result = await run_concierge(text, member_handle=handle, explain_risk=False)
            await self._send(client, chat_id, format_reply(result))
        except Exception as exc:  # noqa: BLE001 — never let one message kill the bot
            await self._send(client, chat_id, f"Sorry, something went wrong: {exc}")

    async def run(self) -> None:
        async with httpx.AsyncClient(timeout=40.0) as client:
            # Clear any webhook and drop the backlog so we only answer fresh
            # messages — avoids replying to stale ones after a restart.
            try:
                await client.get(self._url("deleteWebhook"),
                                 params={"drop_pending_updates": "true"})
            except Exception:
                pass
            print("Concierge Telegram bot is running. Press Ctrl+C to stop.")
            while True:
                try:
                    resp = await client.get(
                        self._url("getUpdates"),
                        params={"offset": self._offset, "timeout": 30},
                    )
                    data = resp.json()
                except Exception as exc:  # noqa: BLE001
                    print(f"getUpdates request failed: {exc!r}")
                    await asyncio.sleep(3)
                    continue
                # Not ok — surface the reason instead of silently spinning. The two
                # 409 Conflicts look identical from outside (no replies) but have
                # opposite fixes:
                #   "...other getUpdates request"      -> another poller; wait it out.
                #   "...webhook is active"             -> a stale webhook is stealing
                #     our updates; deleting it un-wedges us (getMe still says "OK",
                #     so this is invisible to the health check — log it loudly).
                if not data.get("ok"):
                    desc = data.get("description", "")
                    print(f"getUpdates not ok: {desc!r}")
                    if "webhook" in desc.lower():
                        try:
                            await client.get(self._url("deleteWebhook"),
                                             params={"drop_pending_updates": "true"})
                            print("cleared a stale webhook; resuming polling")
                        except Exception:  # noqa: BLE001
                            pass
                    await asyncio.sleep(5)
                    continue
                for upd in data.get("result", []):
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
