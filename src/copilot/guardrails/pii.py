"""Lightweight PII redaction.

For VIP clients, security is part of the product. We strip the obvious
identifiers — emails, phones, passport- and card-like numbers — before any text
reaches a model or a log line. Not a DLP suite; a sane, demonstrable default
that signals data-handling judgment.
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("[EMAIL]", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("[CARD]", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("[PASSPORT]", re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")),
    ("[PHONE]", re.compile(r"\b(?:\+?\d{1,3}[ -]?)?(?:\(?\d{2,4}\)?[ -]?){2,4}\d{2,4}\b")),
]


def redact(text: str) -> str:
    out = text
    for token, pattern in _PATTERNS:
        out = pattern.sub(token, out)
    return out


def has_pii(text: str) -> bool:
    return redact(text) != text
