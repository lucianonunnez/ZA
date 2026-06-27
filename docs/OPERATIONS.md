# Operations — running the bot & the verification agents

## What lives in GitHub (and runs there, using your model key)

These are scheduled "agents" — they run, do their job, report, and stop. GitHub
Actions is the right home for them. They use the model key (GLM via OpenRouter)
from the `OPENROUTER_API_KEY` secret.

| Workflow | What it does | Trigger |
|---|---|---|
| **Health check — connections** (`healthcheck.yml`) | Verifies the live connections (Telegram token via `getMe`, model key via `/key`). Fails (and emails you) if one is down. | every 6h + on demand |
| **Smoke test — real pipeline** (`smoke.yml`) | Runs real quotes end to end with GLM and fails if any route returns no recommendation. The system verifies itself. | every 6h + on demand |
| **Demo — concierge quote** (`demo.yml`) | One quote rendered into the run summary. | on demand |
| **Eval arena** (`arena.yml`) | Multi-model scorecard. | weekly + on demand |
| **Telegram bot (live session)** (`telegram.yml`) | The bot, for a bounded session. See below. | on demand |

Run a health check any time locally too: `copilot doctor`.

## The Telegram bot: how it runs, and the one gotcha

The bot uses **long polling** (`getUpdates`). Telegram allows **only one**
`getUpdates` consumer per token at a time — a second one gets **409 Conflict**.

### What broke (and the fix)
Repeatedly **cancelling + re-triggering** the Actions run briefly overlapped two
pollers → 409 → the loop spun without pausing → the bot got stuck and stopped
answering (even `/start`). Two changes fixed it (`telegram_bot.py`):

1. **`deleteWebhook(drop_pending_updates=true)` on startup** — clears any webhook
   and **drops the backlog**, so a fresh start doesn't flood you with replies to
   old messages.
2. **Back off 5s on any non-ok response (e.g. 409)** instead of spinning — the bot
   **recovers automatically** once it's the only instance.

### Golden rules (so it stays smooth)
- **Start it once.** Don't cancel + restart in a loop — that's what causes 409s
  and message floods. If you must restart, wait ~60s for the old run to fully die.
- **One instance only.** Don't run it in a Codespace *and* in Actions at the same
  time — they fight over `getUpdates` (409).
- **Send one message, wait for the reply.** Don't spam; each message is answered.
- It auto-stops after the chosen minutes (default 50). Re-trigger ~10 min before a
  demo and leave it alone.

## The reliable, always-on path (webhook + a host)

Long polling in ephemeral CI is fine for a bounded demo, not for 24/7. For
always-on, switch to **webhooks**: deploy the FastAPI app (`render.yaml`) to a free
host, then point Telegram at it with `setWebhook`. Telegram *pushes* updates to the
HTTPS endpoint — no polling, no single-instance conflict, no 409. (Planned upgrade.)
