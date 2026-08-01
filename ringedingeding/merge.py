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

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from .models import Answer, Bucket, CallStatus, Participant, Poll, PollKind
from .schemas import OTHER_CHOICE_FIELD
from .slots import SlotIndex

__all__ = [
    "ParticipantResult",
    "Coverage",
    "SlotRow",
    "SlotMerge",
    "ChoiceCount",
    "ChoiceMerge",
    "OpenEntry",
    "OpenMerge",
    "MergeResult",
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
    error: str | None = None

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

    @property
    def total(self) -> int:
        return len(self.answered) + len(self.refused) + len(self.unreached) + len(self.pending)

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
        return self.refused + self.unreached + self.pending

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
        if self.pending:
            parts.append("not called yet: " + ", ".join(r.label for r in self.pending))
        return (
            f"Based on {self.basis} participants. "
            + "; ".join(parts)
            + ". These are not counted as indifferent."
        )


def _classify(participants: Sequence[Participant], answers: dict[str, Answer]) -> Coverage:
    groups: dict[Bucket, list[ParticipantResult]] = {bucket: [] for bucket in Bucket}
    for participant in participants:
        answer = answers.get(
            participant.id,
            Answer(participant_id=participant.id, call_status=CallStatus.PENDING),
        )
        result = ParticipantResult(
            ref=participant.ref,
            name=participant.name,
            phone_masked=participant.phone_masked,
            bucket=answer.bucket,
            status=answer.call_status,
            structured=dict(answer.structured or {}),
            error=answer.error,
        )
        groups[result.bucket].append(result)
    return Coverage(
        answered=tuple(groups[Bucket.ANSWERED]),
        refused=tuple(groups[Bucket.REFUSED]),
        unreached=tuple(groups[Bucket.UNREACHED]),
        pending=tuple(groups[Bucket.PENDING]),
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
    unclear: list[str] = []

    for result in coverage.answered:
        structured = result.structured
        choice = structured.get("choice")
        other_choice = str(structured.get(OTHER_CHOICE_FIELD) or "").strip()
        condition = str(structured.get("condition") or structured.get("note") or "").strip()
        if condition:
            conditions.append((result.label, condition))

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


@dataclass(frozen=True)
class OpenMerge:
    poll: Poll
    coverage: Coverage
    entries: tuple[OpenEntry, ...] = ()

    @property
    def kind(self) -> PollKind:
        return PollKind.OPEN

    @property
    def headline(self) -> str:
        if not self.entries:
            return "No answers collected."
        return (
            f"{len(self.entries)} answer(s) collected, quoted as given. "
            "Free-text answers are never summarised automatically."
        )


def _merge_open(poll: Poll, coverage: Coverage) -> OpenMerge:
    entries = tuple(
        OpenEntry(
            name=result.label,
            answer=str(result.structured.get("answer") or "").strip(),
            note=str(result.structured.get("note") or "").strip(),
        )
        for result in coverage.answered
    )
    return OpenMerge(poll=poll, coverage=coverage, entries=entries)


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
