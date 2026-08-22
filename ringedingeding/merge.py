"""Merging many answers into one result.

The rule that shapes everything in this module:

    **A person who was not reached is never counted as "doesn't mind".**

So no aggregate is ever computed over "everyone". It is computed over the
people who actually answered, and the number of people who did not is carried
alongside the result — with their concrete status, because ``NO_ANSWER``,
``BUSY`` and ``DECLINED`` are three different pieces of news.

A second, quieter rule: silence about a slot is not a "no". If somebody was
asked about Saturday and Sunday and only said "Saturday works", Sunday goes
into ``unknown``, not into ``cannot``. Anything else would fabricate data.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from .models import Answer, Bucket, CallStatus, Participant, Poll, PollKind
from .phone import mask_text
from .schemas import OTHER_CHOICE_FIELD
from .slots import SlotIndex

__all__ = [
    "ChoiceCount",
    "ChoiceMerge",
    "Coverage",
    "MergeResult",
    "OpenEntry",
    "OpenMerge",
    "ParticipantResult",
    "SlotMerge",
    "SlotRow",
    "StanceCount",
    "merge_poll",
]


@dataclass(frozen=True)
class ParticipantResult:
    """One participant plus how their answer counts."""

    ref: str
    name: str
    phone_masked: str
    bucket: Bucket
    status: CallStatus
    structured: dict[str, Any] = field(default_factory=dict)
    transcript: str = ""
    """What was actually said, when the call side provided it.

    The structured fields above are the voice agent's reading of this text. The
    two are reported side by side so the reading can be checked; nothing in the
    merge is computed from the transcript.
    """

    error: str | None = None

    run_id: str | None = None
    """The call this answer came from. Two participants sharing one non-null
    ``run_id`` did not have two separate conversations — see
    :data:`Coverage.shared_call`."""

    shares_call_with: str = ""
    """Set only on an entry moved into :data:`Coverage.shared_call`: the label
    of the participant whose answer from the same call is the one actually
    counted."""

    @property
    def label(self) -> str:
        return self.name or self.ref

    @property
    def status_label(self) -> str:
        return self.status.value


@dataclass(frozen=True)
class Coverage:
    """Who is behind the numbers — and who is not."""

    answered: tuple[ParticipantResult, ...] = ()
    refused: tuple[ParticipantResult, ...] = ()
    unreached: tuple[ParticipantResult, ...] = ()
    pending: tuple[ParticipantResult, ...] = ()

    shared_call: tuple[ParticipantResult, ...] = ()
    """Answered, but the call itself was already counted under a different
    participant who carries the same non-null ``run_id`` — several
    participant records pointing at one real conversation (measured
    2026-08-22: CALL-E can dedupe recipients that share a phone number within
    one dispatch; see FINDINGS.md, "Batch dedup by phone number"). Never
    folded into :data:`answered`: one conversation is counted once, no matter
    how many participant records point at it, and never silently — the
    caveat below always names who is affected."""

    @property
    def total(self) -> int:
        return (
            len(self.answered)
            + len(self.refused)
            + len(self.unreached)
            + len(self.pending)
            + len(self.shared_call)
        )

    @property
    def answered_count(self) -> int:
        return len(self.answered)

    @property
    def is_complete(self) -> bool:
        """True only when every single participant answered."""
        return self.total > 0 and self.answered_count == self.total

    @property
    def missing(self) -> tuple[ParticipantResult, ...]:
        """Everyone who is not in the aggregate, in reporting order."""
        return self.refused + self.unreached + self.pending + self.shared_call

    @property
    def transcribed(self) -> tuple[ParticipantResult, ...]:
        """Everyone whose call came with a transcript.

        Not restricted to the people who answered: a voicemail or a refusal has
        a transcript too, and that is often the one worth reading.
        """
        everybody = (
            self.answered + self.refused + self.unreached + self.pending + self.shared_call
        )
        return tuple(result for result in everybody if result.transcript.strip())

    @property
    def basis(self) -> str:
        return f"{self.answered_count} of {self.total}"

    @property
    def caveat(self) -> str | None:
        """The sentence that has to appear next to any incomplete result."""
        if self.is_complete or self.total == 0:
            return None
        parts: list[str] = []
        if self.unreached:
            detail = ", ".join(
                f"{result.label} ({result.status_label})" for result in self.unreached
            )
            parts.append(f"not reached: {detail}")
        if self.refused:
            parts.append("declined to answer: " + ", ".join(r.label for r in self.refused))
        if self.shared_call:
            detail = ", ".join(
                f"{result.label} (shares a call with {result.shares_call_with})"
                for result in self.shared_call
            )
            parts.append(
                f"share a call with someone already counted, so counted once: {detail}"
            )
        if self.pending:
            parts.append("not called yet: " + ", ".join(r.label for r in self.pending))
        return (
            f"Based on {self.basis} participants. "
            + "; ".join(parts)
            + ". These are not counted as indifferent."
        )


# Live finding, RT-4c 2026-08-22 (R18): a completed call whose identity
# check failed carries no transport-level error at all. The conservative
# Bucket.UNREACHED classification (see Answer.bucket) is correct and does
# not change here -- but a blank Detail column next to "COMPLETED" reads as
# a data gap, not as the deliberate identity-gate refusal it actually is.
#
# Only synthesized when a transcript is present: a COMPLETED call can also
# land in Bucket.UNREACHED because the structured result never arrived at
# all (see the Answer.bucket docstring) -- a different, non-identity
# failure mode this module cannot tell apart from an identity refusal
# without a transcript to point at, so it says nothing rather than guess.
#
# Reworded for R21(b) (user idea, 2026-08-22): the original wording read as
# a plain failure ("the answer was not counted"). The user's own heuristic
# is that a wrong-number call usually corrects itself within seconds --
# a name given back, a stutter, somebody handing the phone over, a hang-up
# -- so a conversation that went ahead normally to the end is itself a
# strong (if unconfirmed) signal this was the right person. The Detail
# column now says so, while the counting stays exactly as conservative as
# before: this is still Bucket.UNREACHED, still excluded from every
# aggregate, until a correction call (see runner.py's is_correction /
# schemas.py's _correction_identity_block, R21a) actually confirms identity.
_UNCONFIRMED_IDENTITY_DETAIL = (
    "call completed and the conversation went normally, so this is "
    "probably the right person — but the identity question was never "
    "confirmed, so the answer is not counted. See the transcript for what "
    "was actually said."
)


def _classify(participants: Sequence[Participant], answers: dict[str, Answer]) -> Coverage:
    groups: dict[Bucket, list[ParticipantResult]] = {bucket: [] for bucket in Bucket}
    for participant in participants:
        answer = answers.get(
            participant.id,
            Answer(participant_id=participant.id, call_status=CallStatus.PENDING),
        )
        error = answer.error
        if answer.completed_but_identity_unconfirmed:
            error = _UNCONFIRMED_IDENTITY_DETAIL
        result = ParticipantResult(
            ref=participant.ref,
            name=participant.name,
            phone_masked=participant.phone_masked,
            bucket=answer.bucket,
            status=answer.call_status,
            structured=dict(answer.structured or {}),
            transcript=answer.transcript or "",
            error=error,
            run_id=answer.run_id,
        )
        groups[result.bucket].append(result)

    # Two participants never get to keep two separate votes over one real
    # conversation (measured 2026-08-22 — see FINDINGS.md, "Batch dedup by
    # phone number", and Coverage.shared_call above). The first participant
    # in poll order who carries a given run_id is the one counted; every
    # later participant with the same run_id moves out of the aggregate and
    # into shared_call, naming who they are duplicating.
    answered: list[ParticipantResult] = []
    shared_call: list[ParticipantResult] = []
    holder_by_run_id: dict[str, ParticipantResult] = {}
    for result in groups[Bucket.ANSWERED]:
        holder = holder_by_run_id.get(result.run_id) if result.run_id else None
        if holder is not None:
            shared_call.append(replace(result, shares_call_with=holder.label))
            continue
        if result.run_id:
            holder_by_run_id[result.run_id] = result
        answered.append(result)

    return Coverage(
        answered=tuple(answered),
        refused=tuple(groups[Bucket.REFUSED]),
        unreached=tuple(groups[Bucket.UNREACHED]),
        pending=tuple(groups[Bucket.PENDING]),
        shared_call=tuple(shared_call),
    )


# --------------------------------------------------------------------------
# slot polls
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SlotRow:
    """One proposed slot and where everybody stands on it."""

    key: str
    label: str
    can: tuple[str, ...] = ()
    cannot: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()
    """Answered, but did not say anything about this slot. Not a 'no'."""

    @property
    def works_for_everyone_who_answered(self) -> bool:
        return bool(self.can) and not self.cannot and not self.unknown


@dataclass(frozen=True)
class SlotMerge:
    poll: Poll
    coverage: Coverage
    rows: tuple[SlotRow, ...] = ()
    common: tuple[SlotRow, ...] = ()
    """Slots that work for every participant who answered."""

    @property
    def kind(self) -> PollKind:
        return PollKind.SLOT

    @property
    def headline(self) -> str:
        if not self.coverage.answered:
            return "No answers yet — no intersection can be computed."
        if not self.common:
            return f"No slot works for all {self.coverage.answered_count} who answered."
        labels = ", ".join(row.label for row in self.common)
        return f"Works for all {self.coverage.answered_count} who answered: {labels}"

    @property
    def ranked(self) -> tuple[SlotRow, ...]:
        """Rows sorted by how many people can make them."""
        return tuple(sorted(self.rows, key=lambda row: (-len(row.can), len(row.cannot), row.label)))


def _as_labels(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Iterable):
        return [str(item) for item in value if str(item).strip()]
    return []


def _merge_slots(poll: Poll, coverage: Coverage) -> SlotMerge:
    index = SlotIndex(poll.slots)
    can_map: dict[str, list[str]] = {}
    cannot_map: dict[str, list[str]] = {}

    # First pass: register every slot anyone mentioned, so an open poll still
    # gets a stable set of rows.
    for result in coverage.answered:
        for label in _as_labels(result.structured.get("available_slots")):
            index.add(label)
        for label in _as_labels(result.structured.get("cannot")):
            index.add(label)

    for result in coverage.answered:
        for label in _as_labels(result.structured.get("available_slots")):
            key = index.key(label)
            if key:
                can_map.setdefault(key, []).append(result.label)
        for label in _as_labels(result.structured.get("cannot")):
            key = index.key(label)
            if key:
                cannot_map.setdefault(key, []).append(result.label)

    answered_labels = [result.label for result in coverage.answered]
    rows: list[SlotRow] = []
    for key in index.keys:
        can = can_map.get(key, [])
        cannot = cannot_map.get(key, [])
        spoken = set(can) | set(cannot)
        unknown = [name for name in answered_labels if name not in spoken]
        rows.append(
            SlotRow(
                key=key,
                label=index.display(key),
                can=tuple(can),
                cannot=tuple(cannot),
                unknown=tuple(unknown),
            )
        )

    common = tuple(row for row in rows if row.works_for_everyone_who_answered)
    return SlotMerge(poll=poll, coverage=coverage, rows=tuple(rows), common=common)


# --------------------------------------------------------------------------
# choice polls
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ChoiceCount:
    option: str
    voters: tuple[str, ...] = ()

    @property
    def count(self) -> int:
        return len(self.voters)


@dataclass(frozen=True)
class ChoiceMerge:
    poll: Poll
    coverage: Coverage
    tally: tuple[ChoiceCount, ...] = ()
    other: tuple[tuple[str, str], ...] = ()
    """Answers outside the offered options: (name, their wording)."""

    abstained: tuple[str, ...] = ()
    """Reached, understood, explicitly no preference. Not a vote, not a refusal."""

    conditions: tuple[tuple[str, str], ...] = ()
    """Qualifiers attached to a vote: (name, wording). Never folded into the count."""

    reasons: tuple[tuple[str, str], ...] = ()
    """Why somebody chose an option, in their own words."""

    concerns: tuple[tuple[str, str], ...] = ()
    """Reservations and counterarguments, kept next to the tally."""

    unclear: tuple[str, ...] = ()
    """Answered, but no option, no 'other', no abstention could be recorded."""

    @property
    def kind(self) -> PollKind:
        return PollKind.CHOICE

    @property
    def leaders(self) -> tuple[ChoiceCount, ...]:
        top = max((entry.count for entry in self.tally), default=0)
        if top == 0:
            return ()
        return tuple(entry for entry in self.tally if entry.count == top)

    @property
    def is_tie(self) -> bool:
        return len(self.leaders) > 1

    @property
    def headline(self) -> str:
        votes = sum(entry.count for entry in self.tally)
        if votes == 0:
            return "No votes were cast."
        leaders = self.leaders
        if self.is_tie:
            names = ", ".join(entry.option for entry in leaders)
            return f"Tie at {leaders[0].count} vote(s): {names}"
        leader = leaders[0]
        return f"Ahead: {leader.option} with {leader.count} of {votes} vote(s) cast"


def _merge_choice(poll: Poll, coverage: Coverage) -> ChoiceMerge:
    voters: dict[str, list[str]] = {option: [] for option in poll.options}
    other: list[tuple[str, str]] = []
    abstained: list[str] = []
    conditions: list[tuple[str, str]] = []
    reasons: list[tuple[str, str]] = []
    concerns: list[tuple[str, str]] = []
    unclear: list[str] = []

    for result in coverage.answered:
        structured = result.structured
        choice = structured.get("choice")
        other_choice = str(structured.get(OTHER_CHOICE_FIELD) or "").strip()
        condition = str(structured.get("condition") or structured.get("note") or "").strip()
        reason = str(structured.get("reason") or "").strip()
        concern_values = _as_labels(structured.get("concerns"))
        if condition:
            conditions.append((result.label, condition))
        if reason:
            reasons.append((result.label, reason))
        concerns.extend((result.label, value) for value in concern_values)

        if isinstance(choice, str) and choice.strip():
            if choice in voters:
                voters[choice].append(result.label)
            else:
                # The agent returned something outside the declared enum.
                # It stays visible instead of being dropped or coerced.
                other.append((result.label, choice.strip()))
            continue
        if other_choice:
            other.append((result.label, other_choice))
            continue
        if structured.get("abstained") is True:
            abstained.append(result.label)
            continue
        unclear.append(result.label)

    tally = tuple(
        ChoiceCount(option=option, voters=tuple(names)) for option, names in voters.items()
    )
    return ChoiceMerge(
        poll=poll,
        coverage=coverage,
        tally=tally,
        other=tuple(other),
        abstained=tuple(abstained),
        conditions=tuple(conditions),
        reasons=tuple(reasons),
        concerns=tuple(concerns),
        unclear=tuple(unclear),
    )


# --------------------------------------------------------------------------
# open polls
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class OpenEntry:
    name: str
    answer: str
    note: str = ""
    stance: str = "unclear"
    reasons: tuple[str, ...] = ()
    concerns: tuple[str, ...] = ()


@dataclass(frozen=True)
class StanceCount:
    stance: str
    people: tuple[str, ...] = ()

    @property
    def count(self) -> int:
        return len(self.people)


@dataclass(frozen=True)
class OpenMerge:
    poll: Poll
    coverage: Coverage
    entries: tuple[OpenEntry, ...] = ()
    tendencies: tuple[StanceCount, ...] = ()

    @property
    def kind(self) -> PollKind:
        return PollKind.OPEN

    @property
    def headline(self) -> str:
        if not self.entries:
            return "No answers collected."
        primary = self.primary_tendency
        if primary is None:
            return self._no_tendency_headline()
        counters = len(self.countervoices)
        suffix = f"; {counters} countervoice(s)" if counters else ""
        return (
            f"Tendency: {primary.stance} ({primary.count} of {len(self.entries)} answers)"
            f"{suffix}."
        )

    def _no_tendency_headline(self) -> str:
        # No single tendency is asserted -- name what people actually said
        # instead of just reporting an absence (FINDINGS.md, live case
        # 2026-08-11: "no single tendency leads" alone hid that two people
        # answered an alternative question with two different, mutually
        # exclusive picks).
        positions = "; ".join(
            f'{entry.name}: "{mask_text(entry.answer)}"'
            for entry in self.entries
            if entry.answer
        )
        if not positions:
            return f"{len(self.entries)} answer(s) collected; no single tendency leads."
        return (
            f"{len(self.entries)} answer(s) collected; no single tendency - "
            f"positions: {positions}."
        )

    @property
    def primary_tendency(self) -> StanceCount | None:
        ranked = sorted(
            (entry for entry in self.tendencies if entry.stance not in ("unclear", "neutral")),
            key=lambda entry: (-entry.count, entry.stance),
        )
        if not ranked or ranked[0].count == 0:
            return None
        if len(ranked) > 1 and ranked[0].count == ranked[1].count:
            return None
        # Live finding, 2026-08-11 (FINDINGS.md): an alternative question
        # ("A or B -- and where?") lets every participant be scored against
        # their OWN pick, so two people who chose mutually exclusive things
        # can both land on "support". A single distinct stance shared by
        # more than one person is not evidence anyone agreed with anyone
        # else -- it means the support/against axis was never used to
        # discriminate between them at all (compare a genuine yes/no
        # question, where "support" and "against" both appear and a leading
        # tendency is a fair claim). One person's own single answer is not
        # manufactured consensus -- there was nobody else who could have
        # used the axis to disagree -- so this only applies once a second
        # voice had the chance to and the data shows the axis stayed silent.
        if len(ranked) < 2 and ranked[0].count > 1:
            return None
        return ranked[0]

    @property
    def countervoices(self) -> tuple[OpenEntry, ...]:
        primary = self.primary_tendency
        if primary is None:
            return ()
        return tuple(
            entry
            for entry in self.entries
            if entry.stance not in (primary.stance, "neutral", "unclear")
        )


def _merge_open(poll: Poll, coverage: Coverage) -> OpenMerge:
    valid_stances = ("support", "against", "mixed", "neutral", "unclear")
    entries = tuple(
        OpenEntry(
            name=result.label,
            answer=str(result.structured.get("answer") or "").strip(),
            note=str(result.structured.get("note") or "").strip(),
            stance=(
                str(result.structured.get("stance") or "unclear").strip().lower()
                if str(result.structured.get("stance") or "unclear").strip().lower()
                in valid_stances
                else "unclear"
            ),
            reasons=tuple(_as_labels(result.structured.get("reasons"))),
            concerns=tuple(_as_labels(result.structured.get("concerns"))),
        )
        for result in coverage.answered
    )
    tendencies = tuple(
        StanceCount(
            stance=stance,
            people=tuple(entry.name for entry in entries if entry.stance == stance),
        )
        for stance in valid_stances
        if any(entry.stance == stance for entry in entries)
    )
    return OpenMerge(
        poll=poll, coverage=coverage, entries=entries, tendencies=tendencies
    )


MergeResult = SlotMerge | ChoiceMerge | OpenMerge


def merge_poll(
    poll: Poll,
    participants: Sequence[Participant],
    answers: dict[str, Answer],
) -> MergeResult:
    """Merge all answers of ``poll`` into one result object."""
    coverage = _classify(participants, answers)
    if poll.kind is PollKind.SLOT:
        return _merge_slots(poll, coverage)
    if poll.kind is PollKind.CHOICE:
        return _merge_choice(poll, coverage)
    return _merge_open(poll, coverage)
