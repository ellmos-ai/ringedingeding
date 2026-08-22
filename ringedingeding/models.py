"""Domain model: polls, participants, call outcomes.

The one invariant worth spelling out: a participant who was never reached is
*not* a participant without an opinion. ``Bucket`` keeps those apart, and every
aggregation in :mod:`ringedingeding.merge` is computed over ``ANSWERED`` only
while reporting the rest verbatim.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .phone import mask, normalize_e164

__all__ = [
    "Answer",
    "Bucket",
    "CallStatus",
    "Participant",
    "ParticipantState",
    "Poll",
    "PollKind",
    "new_id",
]


def new_id(prefix: str) -> str:
    """Short, collision-safe local identifier. Never leaves this machine."""
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class PollKind(StrEnum):
    """What kind of question is being asked."""

    SLOT = "slot"
    """A scheduling question. Merged into an intersection of time slots."""

    CHOICE = "choice"
    """A decision between named options. Merged into a tally."""

    OPEN = "open"
    """A free-text question. Collected verbatim, never auto-summarised."""

    @classmethod
    def parse(cls, value: str) -> PollKind:
        try:
            return cls(str(value).strip().lower())
        except ValueError as error:
            allowed = ", ".join(k.value for k in cls)
            raise ValueError(f"unknown poll kind {value!r} (expected one of: {allowed})") from error


class CallStatus(StrEnum):
    """Call status as reported by CALL-E, plus two local states.

    The upstream set is kept intact on purpose: ``NO_ANSWER`` is not
    ``DECLINED`` is not ``BUSY``. Collapsing them would throw away exactly the
    information the report needs.
    """

    # --- local, never returned by the API ---
    PENDING = "PENDING"
    """Not attempted yet."""

    SKIPPED = "SKIPPED"
    """Deliberately not attempted (aborted run, invalid number)."""

    # --- in flight, reported by CALL-E ---
    PREPARING = "PREPARING"
    """The call is under way. Measured, and easy to get wrong.

    This is what the service reports *while the two sides are talking* — it did
    not move off ``PREPARING`` for an entire conversation and only flipped to
    ``COMPLETED`` some 24 seconds after the call had ended. It is emphatically
    not a failure and not a starting state.
    """

    # --- terminal statuses reported by CALL-E ---
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NO_ANSWER = "NO_ANSWER"
    DECLINED = "DECLINED"
    CANCELED = "CANCELED"
    VOICEMAIL = "VOICEMAIL"
    BUSY = "BUSY"
    EXPIRED = "EXPIRED"

    @classmethod
    def known(cls, value: Any) -> CallStatus | None:
        """Map an API status onto the enum, or ``None`` if it is not one of ours.

        The Developer API documents lowercase statuses (``"completed"``) while
        the MCP/CLI surface documents uppercase ones (``"COMPLETED"``); both are
        accepted. ``CANCELLED`` (two L) is folded into ``CANCELED``.
        """
        if isinstance(value, cls):
            return value
        text = str(value or "").strip().upper().replace("-", "_").replace(" ", "_")
        if text == "CANCELLED":
            return cls.CANCELED
        try:
            return cls(text)
        except ValueError:
            return None

    @classmethod
    def parse(cls, value: Any) -> CallStatus:
        """Like :meth:`known`, but an unrecognised status becomes ``FAILED``.

        Right for the *final* mapping of a finished call, where an
        uninterpretable status must never be read as success. Wrong for
        deciding whether to keep polling — use :meth:`known` there, or a call
        in progress under an unfamiliar status is declared dead mid-sentence.
        """
        return cls.known(value) or cls.FAILED

    @property
    def is_terminal(self) -> bool:
        """Whether this status means the call is over.

        The terminal set is a closed list, so anything else — including a
        status this program has never heard of — means *not finished yet*.
        """
        return self not in (CallStatus.PENDING, CallStatus.PREPARING)


class Bucket(StrEnum):
    """How a participant counts towards the merged result."""

    ANSWERED = "answered"
    """Reached and gave an answer. The only bucket that enters an aggregate."""

    REFUSED = "refused"
    """Reached, chose not to answer. A valid outcome, never argued with."""

    UNREACHED = "unreached"
    """Not reached at all. Carries the concrete status (NO_ANSWER, BUSY, …)."""

    PENDING = "pending"
    """Not attempted yet, or attempt aborted."""


class ParticipantState(StrEnum):
    PENDING = "pending"
    DONE = "done"


@dataclass(frozen=True)
class Participant:
    """One person to call.

    ``ref`` is a short local handle used in fixtures, logs and reports so that
    neither the name nor the number has to be repeated.
    """

    id: str
    poll_id: str
    ref: str
    name: str
    phone_e164: str
    state: ParticipantState = ParticipantState.PENDING
    call_run_id: str | None = None
    attempted_at: str | None = None
    contact_id: str | None = None
    """The address-book entry this participant came from, when there was one."""
    attempt_count: int = 0
    """How many calls have already been placed for this participant.

    Fed into ``safety.idempotency_key`` (measured 2026-08-22, R20b): the
    key was deterministic on ``(poll_id, participant_id)`` alone, so a
    retry after the task text changed reused the exact key from the first
    attempt with a now-different request body -- CALL-E answered with
    ``idempotency_conflict`` (HTTP 409) for both, rather than placing a
    fresh call. Incremented by ``Store.mark_attempted``, once per outcome,
    never by hand."""

    def __post_init__(self) -> None:
        # Validate on construction: an invalid number must never reach a dialer.
        object.__setattr__(self, "phone_e164", normalize_e164(self.phone_e164))

    @property
    def phone_masked(self) -> str:
        return mask(self.phone_e164)

    @property
    def given_name(self) -> str:
        """First token of the name — the only part sent to the voice agent."""
        return self.name.strip().split()[0] if self.name.strip() else self.ref


@dataclass(frozen=True)
class Poll:
    """A question asked to several people."""

    id: str
    question: str
    kind: PollKind
    organizer: str
    language: str = "en"
    region: str = "US"
    locale: str = "en-US"
    options: tuple[str, ...] = ()
    """Answer options for ``choice`` polls."""

    slots: tuple[str, ...] = ()
    """Proposed time windows for ``slot`` polls. Empty means 'open question'."""

    created_at: str = ""
    status: str = "open"

    project_id: str | None = None
    """Set when this poll is one round of a project. ``None`` for a poll made
    straight from the command line — the two are the same thing to everything
    downstream, which is the point of keeping one engine."""

    round_kind: str | None = None
    """``availability`` | ``roundtable`` | ``invitation``. See
    :class:`ringedingeding.projects.RoundKind`."""

    simulated: bool = False
    """True when the answers were invented locally for a rehearsal. Everything
    that displays this poll has to say so."""

    @property
    def has_window(self) -> bool:
        """True when the poll proposes a fixed set of slots.

        With a window the recipient schema can constrain answers to an enum,
        which makes the intersection exact instead of best-effort.
        """
        return bool(self.slots)


@dataclass(frozen=True)
class Answer:
    """What came back for one participant."""

    participant_id: str
    call_status: CallStatus
    structured: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    """The call summary. Untrusted, always masked on output."""

    transcript: str = ""
    """What was said, ``[mm:ss] SPEAKER: Text`` per line.

    Kept next to ``structured`` because the voice agent interprets: it decided
    on its own that "2. Yes, dissatisfied." meant *dissatisfied*. Without the
    wording underneath, that judgement could never be checked. Untrusted text,
    masked on output.
    """

    received_at: str = ""
    run_id: str | None = None
    error: str | None = None

    @property
    def bucket(self) -> Bucket:
        """Classify this answer for the merge step.

        Order matters. ``reachable`` is checked *before* ``refused`` — on
        purpose, and the other way round was a latent bug (found 2026-08-11
        while wiring the identity gate in schemas.py): a call where the wrong
        person answered and, for themselves, declined to continue can come
        back with ``{"reachable": false, "refused": true}``. Checking
        ``refused`` first turned that into this participant's REFUSED, which
        is exactly the misattribution the identity gate exists to prevent —
        a stranger's "no" is not this person's answer. ``reachable`` is
        therefore the earlier, stronger gate: nothing recorded about a call
        counts until the right person was actually confirmed on the line.
        """
        if self.call_status is CallStatus.PENDING:
            return Bucket.PENDING
        if self.call_status is CallStatus.SKIPPED:
            return Bucket.PENDING
        if self.call_status is CallStatus.PREPARING:
            # Still running. Unfinished is not the same as unreachable, and it
            # is certainly not an opinion — it belongs with "not called yet".
            return Bucket.PENDING
        if self.call_status is CallStatus.DECLINED:
            return Bucket.REFUSED
        if self.call_status is not CallStatus.COMPLETED:
            # NO_ANSWER, BUSY, VOICEMAIL, EXPIRED, FAILED, CANCELED
            return Bucket.UNREACHED
        if self.structured.get("reachable") is not True:
            # Every recipient schema requires "reachable" (schemas.py); the
            # agent always fills it in on a real call. A missing or ``None``
            # value is not silence agreeing to be counted — it means the
            # structured result never arrived (audit finding, 2026-08-11:
            # transports/calle.py falls back to ``{}`` when the API sends
            # none), and that must read the same as an explicit ``False``.
            return Bucket.UNREACHED
        if self.structured.get("refused") is True:
            return Bucket.REFUSED
        return Bucket.ANSWERED

    @property
    def completed_but_identity_unconfirmed(self) -> bool:
        """True when the call finished, produced a transcript, but the agent
        never confirmed it was speaking to the intended person.

        This is the "probably the right person, unconfirmed" case (R18/R21):
        the conservative ``Bucket.UNREACHED`` classification above is still
        correct and unaffected by this property -- it exists so that
        ``merge.py`` (the report's Detail column) and ``runner.py`` (whether
        a ``--retry`` becomes a correction call, R21) share exactly one
        definition of this case rather than two that could quietly drift
        apart. An existing transport-level ``error`` always takes priority
        and disqualifies this: that is a different, more concrete failure,
        not an identity refusal.
        """
        return (
            self.error is None
            and self.call_status is CallStatus.COMPLETED
            and self.structured.get("reachable") is not True
            and bool(self.transcript.strip())
        )
