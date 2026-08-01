"""The dry-run transport: scripted outcomes, no account, no network.

This is not a stub that returns "OK". It runs the whole pipeline — schema
generation, per-recipient payload assembly, status mapping, merging, reporting
— and validates each scripted answer against the schema the voice agent would
have received. A fixture that could not have come out of a real call therefore
fails the dry run instead of quietly passing it.
"""

from __future__ import annotations

import time
from typing import Any

from ..models import CallStatus
from ..validate import validate
from .base import CallOutcome, CallRequest, CallTransport

__all__ = ["FixtureTransport", "FixtureOutcomeMissing"]


class FixtureOutcomeMissing(KeyError):
    """A participant has no scripted outcome in the fixture."""


class FixtureTransport(CallTransport):
    """Replays scripted call outcomes keyed by participant ``ref``."""

    name = "fixture"
    supports_batch = True
    is_live = False

    def __init__(
        self,
        outcomes: dict[str, dict[str, Any]],
        *,
        latency_seconds: float = 0.0,
        check_schema: bool = True,
    ) -> None:
        self.outcomes = dict(outcomes or {})
        self.latency_seconds = max(0.0, float(latency_seconds))
        self.check_schema = check_schema

    def place_one(self, request: CallRequest) -> CallOutcome:
        ref = request.participant.ref
        spec = self.outcomes.get(ref)
        if spec is None:
            raise FixtureOutcomeMissing(
                f"fixture has no outcome for participant ref {ref!r}; "
                "every participant needs one, otherwise the dry run would "
                "invent a result"
            )

        if self.latency_seconds:
            time.sleep(self.latency_seconds)

        status = CallStatus.parse(spec.get("call_status", "COMPLETED"))
        structured: dict[str, Any] = dict(spec.get("structured_result") or {})
        summary = str(spec.get("summary") or "")
        # Optional. A scripted transcript is what lets the dry run show the
        # wording underneath an interpreted answer, the same way a live call
        # does — a call that reached a mailbox has one too.
        transcript = str(spec.get("transcript") or "")

        # A call that never connected cannot carry a filled-in schema.
        if status not in (CallStatus.COMPLETED, CallStatus.DECLINED) and structured:
            return CallOutcome(
                participant_id=request.participant.id,
                status=CallStatus.FAILED,
                error=(
                    f"fixture for {ref!r} claims status {status.value} but also "
                    "carries a structured result; that combination cannot occur"
                ),
            )

        if self.check_schema and structured:
            violations = validate(structured, request.recipient_schema)
            if violations:
                return CallOutcome(
                    participant_id=request.participant.id,
                    status=CallStatus.FAILED,
                    error=f"fixture for {ref!r} violates the recipient schema: "
                    + "; ".join(violations),
                )

        return CallOutcome(
            participant_id=request.participant.id,
            status=status,
            structured=structured,
            summary=summary,
            transcript=transcript,
            run_id=f"fixture_{ref}",
        )
