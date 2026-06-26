"""FastAPI surface — same pipeline, exposed as an HTTP endpoint.

    uvicorn copilot.api:app --reload
    POST /quote {"message": "..."}  ->  brief + recommendation + trace

This is the "owned production system" shape: a typed request in, a typed response
out, with the cost/latency trace attached so ops can see what every call cost.
FastAPI is Luciano's core framework; the Django port is a documented first-week task.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from copilot.config import settings
from copilot.pipeline import run_concierge
from copilot.schemas import Recommendation, TripBrief

app = FastAPI(title="Ascend Concierge Copilot", version="0.1.0")


class QuoteRequest(BaseModel):
    message: str
    member_handle: str | None = None


class QuoteResponse(BaseModel):
    brief: TripBrief
    recommendation: Recommendation
    trace: dict


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": settings.resolve_provider()}


@app.post("/quote", response_model=QuoteResponse)
async def quote(req: QuoteRequest) -> QuoteResponse:
    result = await run_concierge(req.message, member_handle=req.member_handle or None)
    return QuoteResponse(
        brief=result.brief,
        recommendation=result.recommendation,
        trace=result.trace,
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """A tiny self-contained web UI so you can see it run in a browser."""
    return _INDEX_HTML


_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Ascend Concierge Copilot</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: -apple-system, system-ui, sans-serif; background:#0b0e14; color:#e6e6e6;
         margin:0; padding:2rem; display:flex; justify-content:center; }
  .wrap { width:100%; max-width:760px; }
  h1 { font-size:1.4rem; margin:0 0 .25rem; }
  p.sub { color:#8a94a6; margin:0 0 1.5rem; }
  textarea { width:100%; box-sizing:border-box; background:#141925; color:#e6e6e6;
             border:1px solid #283042; border-radius:10px; padding:.8rem; font-size:1rem; }
  .row { display:flex; gap:.6rem; margin-top:.6rem; flex-wrap:wrap; }
  input { background:#141925; color:#e6e6e6; border:1px solid #283042; border-radius:10px;
          padding:.6rem .8rem; font-size:.95rem; }
  button { background:#3b82f6; color:#fff; border:0; border-radius:10px; padding:.7rem 1.4rem;
           font-size:1rem; cursor:pointer; }
  button:disabled { opacity:.5; cursor:wait; }
  .card { background:#141925; border:1px solid #283042; border-radius:12px; padding:1rem 1.2rem;
          margin-top:1.2rem; }
  table { width:100%; border-collapse:collapse; font-size:.92rem; }
  th,td { text-align:left; padding:.45rem .4rem; border-bottom:1px solid #222a38; }
  .star { color:#fbbf24; }
  .msg { background:#0f1521; border-left:3px solid #22c55e; padding:.8rem 1rem; border-radius:8px;
         margin-top:.8rem; }
  .meta { color:#8a94a6; font-size:.8rem; margin-top:.8rem; }
  .band-low{color:#22c55e}.band-moderate{color:#eab308}.band-elevated{color:#f97316}.band-high{color:#ef4444}
</style>
</head>
<body>
<div class="wrap">
  <h1>✈️ Ascend Concierge Copilot</h1>
  <p class="sub">A messy traveler request → a quoted, risk-scored, points-optimized recommendation.</p>
  <textarea id="req" rows="3">I need NYC to London next Thursday, business class, prefer a morning arrival, budget is flexible</textarea>
  <div class="row">
    <input id="member" placeholder="member handle (optional)" />
    <button id="go" onclick="run()">Get recommendation</button>
  </div>
  <div id="out"></div>
</div>
<script>
async function run() {
  const btn = document.getElementById('go'); btn.disabled = true; btn.textContent = 'Thinking…';
  const out = document.getElementById('out'); out.innerHTML = '';
  try {
    const res = await fetch('/quote', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ message: document.getElementById('req').value,
                             member_handle: document.getElementById('member').value || null })
    });
    const d = await res.json();
    const b = d.brief, rec = d.recommendation, t = d.trace;
    let rows = rec.options.map((o,i) => {
      const f=o.flight, r=o.risk, star = i===rec.recommended_index ? '<span class="star">★</span>' : '';
      const save = f.savings_pct ? f.savings_pct.toFixed(0)+'%' : '—';
      return `<tr><td>${star}</td><td>${f.carrier} ${f.flight_no}</td><td>${f.depart}</td>
        <td>$${f.cash_price_usd.toLocaleString()}</td><td>${save}</td>
        <td class="band-${r.band}">${r.score.toFixed(0)} ${r.band}</td></tr>`;
    }).join('');
    out.innerHTML = `<div class="card">
      <strong>${b.origin} → ${b.destination}</strong> · ${b.cabin} · ${b.passengers} pax
      <table><thead><tr><th></th><th>Flight</th><th>Depart</th><th>Cash</th><th>Points save</th><th>Risk</th></tr></thead>
      <tbody>${rows}</tbody></table>
      ${rec.whatsapp_message ? `<div class="msg">📱 ${rec.whatsapp_message}</div>` : ''}
      <div class="meta">provider=${t.by_model ? Object.keys(t.by_model).join(', ') : '—'}
        · calls=${t.calls} · cost=$${t.total_cost_usd.toFixed(4)} · fallbacks=${t.fallbacks}</div>
    </div>`;
  } catch (e) {
    out.innerHTML = `<div class="card">Error: ${e}</div>`;
  } finally { btn.disabled = false; btn.textContent = 'Get recommendation'; }
}
</script>
</body>
</html>
"""
