"""Guardrails: keep sensitive data out of prompts, logs, and traces."""

from copilot.guardrails.pii import redact

__all__ = ["redact"]
