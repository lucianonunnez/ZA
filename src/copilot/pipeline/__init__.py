"""The concierge pipeline: extract -> flights -> risk -> recommend."""

from copilot.pipeline.orchestrator import ConciergeResult, run_concierge

__all__ = ["run_concierge", "ConciergeResult"]
