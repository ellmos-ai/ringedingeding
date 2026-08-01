"""The rehearsal transport: invented answers, clearly marked as invented.

Why this exists at all
----------------------

The command line refuses to simulate a poll of real people, and it is right to:
there is nothing to simulate it from, and a made-up answer that looks like a
real one is the worst output this program could produce.

The browser has a different problem. Without any answers a person never gets to
see the calendar, the four states, the criteria or the decision — the entire
second half of the tool is unreachable until money has been spent on real calls.
So there is a third mode next to *dry run* and *live*: a **rehearsal** that
invents plausible answers locally.

What keeps it honest
--------------------

* The poll it writes into is flagged ``simulated=1`` in the database, and every
  screen that shows such a poll carries a banner saying the answers were made up.
* The answers are **deterministic** — the same person in the same project always
  produces the same result — so a rehearsal is reproducible and obviously not a
  recording of anything that happened.
* Every generated result is checked against the same recipient schema the voice
  agent would have to fill in. A rehearsal that could not have come out of a real
  call fails instead of passing quietly.
* A realistic mix is generated on purpose, including people who are not reached.
  A rehearsal in which everybody answers would teach the wrong lesson about what
  this tool is for.

Nothing here can dial anything: ``is_live`` is ``False`` and there is no network
code in this module.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..models import CallStatus, PollKind
from ..validate import validate
from .base import CallOutcome, CallRequest, CallTransport

__all__ = ["RehearsalTransport", "REHEARSAL_NOTE"]

REHEARSAL_NOTE = "SIMULATED — this answer was generated locally, no call was made"

# Roughly one in five people is not reached. The two statuses are different
# pieces of news and the result view has to be able to show both.
_UNREACHED = (
    (0.72, CallStatus.NO_ANSWER),
    (0.86, CallStatus.VOICEMAIL),
    (0.93, CallStatus.BUSY),
)


class RehearsalTransport(CallTransport):
    """Generates schema-valid answers without touching the network."""

    name = "rehearsal"
    supports_batch = True
    is_live = False

    def __init__(self, *, seed: str = "") -> None:
        self.seed = seed

    # -- deterministic pseudo-randomness ------------------------------------

    def _fraction(self, *parts: str) -> float:
        """A stable number in ``[0, 1)`` for this seed and these parts."""
        digest = hashlib.sha256(("|".join((self.seed, *parts))).encode("utf-8")).digest()
        return int.from_bytes(digest[:4], "big") / 2**32

    # -- generation ---------------------------------------------------------

    def place_one(self, request: CallRequest) -> CallOutcome:
        ref = request.participant.ref
        roll = self._fraction(request.poll.id, ref, "reached")

        if roll >= _UNREACHED[0][0]:
            status = next(
                (status for threshold, status in _UNREACHED if roll < threshold),
                CallStatus.DECLINED,
            )
            if status is CallStatus.DECLINED:
                # Reached, but chose not to answer. A valid outcome, and one the
                # report has to keep apart from "not reached".
                return self._outcome(
                    request,
                    CallStatus.COMPLETED,
                    {"reachable": True, "refused": True},
                    "Wanted to be left out of this one.",
                )
            return self._outcome(request, status, {}, "Nobody picked up.")

        structured = self._structured(request)
        return self._outcome(request, CallStatus.COMPLETED, structured, "Answered.")

    def _structured(self, request: CallRequest) -> dict[str, Any]:
        poll = request.poll
        ref = request.participant.ref
        base: dict[str, Any] = {"reachable": True, "refused": False}

        if poll.kind is PollKind.SLOT:
            can: list[str] = []
            cannot: list[str] = []
            for slot in poll.slots:
                roll = self._fraction(poll.id, ref, slot)
                if roll < 0.55:
                    can.append(slot)
                elif roll < 0.9:
                    cannot.append(slot)
                # The remaining tenth is said about neither, which is exactly
                # the "did not mention it" case the merge treats as unknown.
            base["available_slots"] = can
            base["cannot"] = cannot
            return base

        if poll.kind is PollKind.CHOICE and poll.options:
            index = int(self._fraction(poll.id, ref, "choice") * len(poll.options))
            base["choice"] = poll.options[min(index, len(poll.options) - 1)]
            return base

        base["answer"] = "Sounds good to me."
        return base

    def _outcome(
        self,
        request: CallRequest,
        status: CallStatus,
        structured: dict[str, Any],
        summary: str,
    ) -> CallOutcome:
        if structured:
            violations = validate(structured, request.recipient_schema)
            if violations:
                # A generator that cannot satisfy its own schema is a bug in this
                # file, and it has to surface as one rather than as an answer.
                return CallOutcome(
                    participant_id=request.participant.id,
                    status=CallStatus.FAILED,
                    error="rehearsal produced an answer the schema rejects: "
                    + "; ".join(violations),
                )
        return CallOutcome(
            participant_id=request.participant.id,
            status=status,
            structured=structured,
            summary=f"[{REHEARSAL_NOTE}] {summary}",
            run_id=f"rehearsal_{request.participant.ref}",
        )
