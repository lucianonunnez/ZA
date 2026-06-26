"""FastAPI surface — same pipeline, exposed as an HTTP endpoint.

    uvicorn copilot.api:app --reload
    POST /quote {"message": "..."}  ->  brief + recommendation + trace

This is the "owned production system" shape: a typed request in, a typed response
out, with the cost/latency trace attached so ops can see what every call cost.
FastAPI is Luciano's core framework; the Django port is a documented first-week task.
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from copilot.pipeline import run_concierge
from copilot.schemas import Recommendation, TripBrief

app = FastAPI(title="Ascend Concierge Copilot", version="0.1.0")


class QuoteRequest(BaseModel):
    message: str


class QuoteResponse(BaseModel):
    brief: TripBrief
    recommendation: Recommendation
    trace: dict


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/quote", response_model=QuoteResponse)
async def quote(req: QuoteRequest) -> QuoteResponse:
    result = await run_concierge(req.message)
    return QuoteResponse(
        brief=result.brief,
        recommendation=result.recommendation,
        trace=result.trace,
    )
