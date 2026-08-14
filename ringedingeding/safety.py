"""Guard rails that have to hold before anything is dialed.

Three separate concerns live here:

1. **Sensitive content.** Automated calls must not carry medical, legal,
   financial or emergency traffic. Such a poll is refused at creation time,
   not at dial time — refusing early means the number is never even stored.
2. **Live confirmation.** Placing real calls requires an explicit, typed
   confirmation on top of the ``--live`` flag.
3. **Idempotency.** A deterministic key per (poll, participant, attempt) so a
   repeated run cannot produce a second call for the same intent.

The keyword lists are intentionally narrow. They target *advice-seeking* and
*emergency* phrasing, not any mention of a doctor or a price — the family poll
"shall we give grandma a photo book, under 50 euros?" must pass.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

__all__ = [
    "LIVE_CONFIRMATION_PHRASE",
    "LiveCallBlocked",
    "SensitiveContent",
    "SensitiveFinding",
    "assert_question_allowed",
    "check_question",
    "idempotency_key",
]

LIVE_CONFIRMATION_PHRASE = "CALL THEM"
"""What the operator has to type before real calls are placed."""


class SensitiveContent(ValueError):
    """Raised when a question falls into a category we refuse to phone about."""


class LiveCallBlocked(RuntimeError):
    """Raised when live dialing is attempted without explicit confirmation."""


@dataclass(frozen=True)
class SensitiveFinding:
    category: str
    matched: str
    explanation: str


def _pattern(*words: str) -> re.Pattern[str]:
    # \b does not work well across German compounds, so match on word starts.
    joined = "|".join(re.escape(word) for word in words)
    return re.compile(rf"(?<![\w]){joined}", re.IGNORECASE)


_CATEGORIES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "emergency",
        _pattern(
            "notfall", "notarzt", "notruf", "lebensgefahr", "suizid", "selbstmord",
            "emergency", "ambulance", "suicide", "urgent care", "911", "112",
        ),
        "Emergency traffic must reach a human service directly, never an automated call.",
    ),
    (
        "medical",
        _pattern(
            "diagnose", "symptom", "medikament", "dosierung", "behandlung",
            "therapieempfehlung", "befund", "blutwert",
            "diagnosis", "symptoms", "medication", "dosage", "prescription",
            "medical advice", "treatment plan",
        ),
        "Medical questions need a qualified human, not a voice agent.",
    ),
    (
        "legal",
        _pattern(
            "rechtsberatung", "klage einreichen", "anwaltlich", "strafanzeige",
            "kündigungsschutz", "vollmacht erteilen",
            "legal advice", "lawsuit", "sue ", "power of attorney", "press charges",
        ),
        "Legal advice must not be gathered or given by an automated call.",
    ),
    (
        "financial",
        _pattern(
            "anlageberatung", "geldanlage", "aktien kaufen", "kredit aufnehmen",
            "kontodaten", "iban", "pin ", "tan ", "überweisung tätigen",
            "investment advice", "buy shares", "take out a loan", "bank details",
            "credit card number", "account number",
        ),
        "Financial instructions and bank details must never travel through a call agent.",
    ),
)


def check_question(text: str) -> list[SensitiveFinding]:
    """Return every sensitive-content finding for ``text`` (empty list = fine)."""
    haystack = text or ""
    findings: list[SensitiveFinding] = []
    for category, pattern, explanation in _CATEGORIES:
        match = pattern.search(haystack)
        if match:
            findings.append(
                SensitiveFinding(
                    category=category,
                    matched=match.group(0).strip(),
                    explanation=explanation,
                )
            )
    return findings


def assert_question_allowed(*parts: str) -> None:
    """Raise :class:`SensitiveContent` if any part hits a refused category."""
    findings = check_question(" \n ".join(part for part in parts if part))
    if not findings:
        return
    lines = [
        f"- {finding.category}: matched {finding.matched!r} — {finding.explanation}"
        for finding in findings
    ]
    raise SensitiveContent(
        "This question is not suitable for an automated phone poll:\n"
        + "\n".join(lines)
        + "\n\nRingedingeding refuses these categories by design. "
        "There is no override flag."
    )


def idempotency_key(poll_id: str, participant_id: str, attempt: int = 1) -> str:
    """Stable key for one dial intent.

    Deterministic on purpose: re-running the same poll for the same participant
    produces the same key, so the CALL-E side can reject the duplicate even if
    our local state was lost.
    """
    seed = f"ringedingeding:{poll_id}:{participant_id}:{attempt}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    return f"rdd_{digest}"
