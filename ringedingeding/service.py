"""The application layer — one flow, three ways in.

Everything a person does with Ringedingeding happens here: name the occasion,
pick candidate dates, pick people, choose the wording, look at the order text,
place the calls, read the board, set the criteria, decide, invite.

The command line, ``SKILL.md`` and the web interface all call **these**
functions and add nothing of their own. That is not tidiness for its own sake:
the moment the browser grows a rule the command line does not have, there are
two products with one name.

The order of the functions below is the order of the questions an agent would
ask. Reading this file top to bottom is reading the interview.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Iterable, Sequence

from .activity import ActivityLine
from .fixtures import Fixture, load_fixture, placeholder_numbers, resolve_fixture
from .merge import Coverage, MergeResult, ParticipantResult, merge_poll
from .models import Participant, Poll, PollKind
from .projects import (
    Contact,
    Criteria,
    DateKind,
    Decision,
    Invitee,
    Project,
    ProjectMode,
    ProjectQuestion,
    ProjectState,
    ProjectStore,
    RoundKind,
    Slot,
    slot_label,
)
from .runner import RunReport, build_requests, run_poll
from .safety import LIVE_CONFIRMATION_PHRASE, LiveCallBlocked, assert_question_allowed
from .slots import SlotIndex
from .store import Store
from .timings import estimate_seconds, format_duration
from .transports.base import CallRequest, CallTransport
from .transports.fixture import FixtureTransport
from .transports.rehearsal import RehearsalTransport

__all__ = [
    "RunMode",
    "COST_PER_CALL_USD",
    "Person",
    "SlotView",
    "Board",
    "Preview",
    "create_project",
    "set_dates",
    "day_slot_specs",
    "set_invitees",
    "resync_contact",
    "set_wording",
    "wording",
    "availability_round",
    "set_advisor_question",
    "advisor_question",
    "roundtable_round",
    "invitation_round",
    "default_invitation_text",
    "preview",
    "make_transport",
    "run_round",
    "board",
    "AdvisorBoard",
    "advisor_board",
    "set_criteria",
    "decide",
    "question_for",
]

COST_PER_CALL_USD = 0.05
"""Documented CALL-E price: per call, not per minute."""

GREETING = "greeting"
CLOSING = "closing"


class RunMode:
    """How a round is carried out. Three of the four never touch a telephone."""

    PLAN = "plan"
    """Show what would happen. Nothing is called, nothing is written."""

    SCRIPT = "script"
    """Replay the scripted answers of a fixture. Needs a fixture-backed project."""

    REHEARSAL = "rehearsal"
    """Invent answers locally so the rest of the flow can be inspected.
    Marks the round as simulated; every view has to say so."""

    LIVE = "live"
    """Real telephones. Requires the typed confirmation."""

    ALL = (PLAN, SCRIPT, REHEARSAL, LIVE)
    WITHOUT_CALLS = (PLAN, SCRIPT, REHEARSAL)


# --------------------------------------------------------------------------
# 1. "Um was geht's?"
# --------------------------------------------------------------------------


def create_project(
    projects: ProjectStore,
    *,
    occasion: str,
    organizer: str,
    mode: str = ProjectMode.SCHEDULE,
    date_kind: str = DateKind.DAY_SLOTS,
    language: str = "de",
    region: str | None = None,
    locale: str | None = None,
    urgency: str = "",
    group_id: str | None = None,
    fixture_name: str | None = None,
) -> Project:
    """Create a project. The occasion is checked for refused content first.

    ``region``/``locale`` left unset (``None``) are derived from ``language``
    one layer down, in :meth:`ProjectStore.create_project` — this wrapper
    only needs to not shadow that with hardcoded defaults of its own (it did,
    until 2026-08-11: an English project made through the web UI, which never
    sends a region at all, kept this function's old "DE" default regardless).

    Refusing here rather than at dial time means a medical or emergency subject
    never gets as far as being attached to somebody's phone number.
    """
    assert_question_allowed(occasion)
    project = projects.create_project(
        occasion=occasion,
        organizer=organizer,
        mode=mode,
        date_kind=date_kind,
        language=language,
        region=region,
        locale=locale,
        urgency=urgency,
        group_id=group_id,
        fixture_name=fixture_name,
    )
    if group_id:
        group = projects.group(group_id)
        projects.set_invitees(project.id, [contact.id for contact in group.members])
    return project


def question_for(project: Project) -> str:
    """The sentence the voice agent will ask, word for word.

    Derived from the occasion rather than asked for separately: the person
    already said what it is about, and asking them to phrase it twice is how
    forms get long.
    """
    occasion = project.occasion.rstrip(" .!?")
    if project.is_german:
        return f"Es geht um {occasion}. Wann von diesen Zeiten könntest du?"
    return f"It is about {occasion}. Which of these times could you make?"


# --------------------------------------------------------------------------
# 2.-6. "Welche Tage? Welche Zeiten? Weicht ein Tag ab?"
# --------------------------------------------------------------------------


def day_slot_specs(
    project: Project,
    *,
    days: Sequence[str],
    default_times: Sequence[tuple[str, str]] = (),
    overrides: dict[str, Sequence[tuple[str, str]]] | None = None,
    whole_day: bool = False,
) -> list[dict[str, Any]]:
    """Turn "these days, these standard times, except here" into slot rows.

    This is the shape of the product concept made literal: one standard set of
    times applied to every chosen day, and then a per-day exception list that
    wins where it exists. A day whose override is an empty list keeps the day
    but drops every time slot — which is how somebody says "not that day after
    all" without unpicking their standard times.
    """
    exceptions = {str(key): list(value) for key, value in (overrides or {}).items()}
    specs: list[dict[str, Any]] = []
    for day in days:
        day_text = str(day).strip()
        if not day_text:
            continue
        try:
            date.fromisoformat(day_text)
        except ValueError:
            raise ValueError(f"{day_text!r} is not a date (expected YYYY-MM-DD)") from None

        if whole_day or project.date_kind == DateKind.WHOLE_DAY:
            specs.append({"day_date": day_text, "all_day": True})
            continue

        times = exceptions.get(day_text, list(default_times))
        for start, end in times:
            specs.append(
                {"day_date": day_text, "start_time": start, "end_time": end, "all_day": False}
            )
    return specs


def set_dates(
    store: Store,
    projects: ProjectStore,
    project: Project,
    specs: Sequence[dict[str, Any]],
) -> list[Slot]:
    """Replace the candidate dates and keep the running round in step.

    The poll's window has to be rewritten alongside, because the labels in it
    are what the voice agent reads out and what comes back in the answers. Slots
    that survive keep their answers; a slot that disappears takes its column
    with it and leaves the answers of the others alone.
    """
    slots = projects.replace_slots(project, specs)
    poll_ids = projects.round_ids(project.id, RoundKind.AVAILABILITY)
    for poll_id in poll_ids:
        store.set_poll_window(poll_id, [slot.label for slot in slots])
    return slots


# --------------------------------------------------------------------------
# 7. "Wen möchtest du einladen?"
# --------------------------------------------------------------------------


def set_invitees(
    store: Store,
    projects: ProjectStore,
    project: Project,
    contact_ids: Sequence[str],
) -> list[Invitee]:
    """Set the guest list and bring every existing round in line with it."""
    invitees = projects.set_invitees(project.id, contact_ids)
    for kind in (RoundKind.AVAILABILITY, RoundKind.ROUNDTABLE, RoundKind.INVITATION):
        for poll_id in projects.round_ids(project.id, kind):
            sync_participants(store, store.get_poll(poll_id), invitees)
    return invitees


def uncallable(invitees: Sequence[Invitee]) -> list[Contact]:
    """Everybody on the guest list who has no phone number.

    The fourth state of the result view. It lives here, one level above the
    call, because these people never become participants of a round at all —
    which is precisely why they must not silently vanish from the report.
    """
    return [
        invitee.contact
        for invitee in invitees
        if invitee.contact is not None and not invitee.contact.callable
    ]


def resync_contact(store: Store, projects: ProjectStore, contact_id: str) -> list[Project]:
    """Bring every round that invited this contact back in line with the book.

    This is what makes "Kontaktdaten nachtragen, Anruf wird nachgeholt" true.
    Adding a phone number changes whether somebody can be called at all, and
    without this the person would be neither in the round nor in the list of
    people who could not be reached — they would simply disappear from the
    report, which is the one outcome this project refuses everywhere else.
    """
    touched: list[Project] = []
    for project in projects.projects():
        invitees = projects.invitees(project.id)
        if not any(invitee.contact_id == contact_id for invitee in invitees):
            continue
        for kind in (RoundKind.AVAILABILITY, RoundKind.ROUNDTABLE, RoundKind.INVITATION):
            for poll_id in projects.round_ids(project.id, kind):
                sync_participants(store, store.get_poll(poll_id), invitees)
        touched.append(project)
    return touched


def sync_participants(
    store: Store, poll: Poll, invitees: Sequence[Invitee]
) -> list[Participant]:
    """Make the round's participants match the callable part of the guest list.

    Additive by default: somebody who gained a phone number is added and gets
    called on the next run, which is how "Kontaktdaten nachtragen, Anruf wird
    nachgeholt" works — no special path, the runner simply finds one more person
    who has no answer yet.

    Removal only ever touches participants **without** an answer. An answer that
    has been given is a fact about the world and is not deleted because somebody
    was taken off a list.
    """
    existing = store.participants(poll.id)
    answers = store.answers(poll.id)
    by_contact = {p.contact_id: p for p in existing if p.contact_id}
    wanted = {
        invitee.contact.id: invitee.contact
        for invitee in invitees
        if invitee.contact is not None and invitee.contact.callable
    }

    for contact_id, contact in wanted.items():
        if contact_id in by_contact:
            continue
        store.add_participant(
            poll.id, name=contact.name, phone=contact.phone or "", contact_id=contact_id
        )

    for contact_id, participant in by_contact.items():
        if contact_id not in wanted and participant.id not in answers:
            store.delete_participant(participant.id)

    return store.participants(poll.id)


# --------------------------------------------------------------------------
# 8. "Wie soll begrüßt und verabschiedet werden?"
# --------------------------------------------------------------------------


def set_wording(
    projects: ProjectStore,
    project: Project,
    *,
    greeting: Sequence[str] = (),
    closing: Sequence[str] = (),
) -> tuple[list[str], list[str]]:
    """Store the organizer's own sentences.

    Checked for refused content like any other text that will be spoken: a
    greeting is not a loophole around :func:`assert_question_allowed`.
    """
    assert_question_allowed(*greeting, *closing)
    projects.set_phrases(GREETING, greeting, scope="project", scope_id=project.id)
    projects.set_phrases(CLOSING, closing, scope="project", scope_id=project.id)
    return wording(projects, project)


def wording(projects: ProjectStore, project: Project) -> tuple[list[str], list[str]]:
    greeting = [p.text for p in projects.phrases(GREETING, scope="project", scope_id=project.id)]
    closing = [p.text for p in projects.phrases(CLOSING, scope="project", scope_id=project.id)]
    return greeting, closing


# --------------------------------------------------------------------------
# rounds
# --------------------------------------------------------------------------


def availability_round(
    store: Store, projects: ProjectStore, project: Project, *, create: bool = True
) -> Poll | None:
    """The "when can you" round of this project — created once, run as often as needed.

    Deliberately *one* poll rather than one per run. Calling the people who were
    not reached last time is then not a second round with its own bookkeeping:
    it is the same round run again, and the runner already skips everybody who
    has an answer.
    """
    existing = projects.round_ids(project.id, RoundKind.AVAILABILITY)
    if existing:
        return store.get_poll(existing[0])
    if not create:
        return None

    slots = projects.slots(project.id)
    poll = store.create_poll(
        question=question_for(project),
        kind=PollKind.SLOT,
        organizer=project.organizer,
        language=project.language,
        region=project.region,
        locale=project.locale,
        slots=[slot.label for slot in slots],
        project_id=project.id,
        round_kind=RoundKind.AVAILABILITY,
    )
    sync_participants(store, poll, projects.invitees(project.id))
    return poll


def set_advisor_question(
    projects: ProjectStore,
    project: Project,
    question: str,
    *,
    options: Sequence[str] = (),
) -> ProjectQuestion:
    """Store the Advisor prompt and keep an unrun preview round in sync."""
    if project.mode != ProjectMode.ROUNDTABLE:
        raise ValueError("advisor questions belong to an Ask your Advisor project")
    clean_question = question.strip()
    if not clean_question:
        raise ValueError("the advisor question must not be empty")
    assert_question_allowed(clean_question)
    clean_options = tuple(
        dict.fromkeys(str(value).strip() for value in options if str(value).strip())
    )
    kind = PollKind.CHOICE if len(clean_options) >= 2 else PollKind.OPEN
    saved = projects.set_questions(
        [clean_question],
        kind=kind.value,
        options=clean_options,
        scope="project",
        scope_id=project.id,
    )[0]
    for poll_id in projects.round_ids(project.id, RoundKind.ROUNDTABLE):
        projects.store.set_poll_definition(
            poll_id, question=saved.text, kind=kind, options=saved.options
        )
    return saved


def advisor_question(projects: ProjectStore, project: Project) -> ProjectQuestion | None:
    questions = projects.questions(scope="project", scope_id=project.id)
    return questions[0] if questions else None


def roundtable_round(
    store: Store, projects: ProjectStore, project: Project, *, create: bool = True
) -> Poll | None:
    """The one opinion round of an Ask your Advisor project."""
    existing = projects.round_ids(project.id, RoundKind.ROUNDTABLE)
    if existing:
        return store.get_poll(existing[0])
    if not create:
        return None
    configured = advisor_question(projects, project)
    if configured is None:
        raise ValueError("set the advisor question before preparing the round")
    poll = store.create_poll(
        question=configured.text,
        kind=configured.kind,
        organizer=project.organizer,
        language=project.language,
        region=project.region,
        locale=project.locale,
        options=configured.options,
        project_id=project.id,
        round_kind=RoundKind.ROUNDTABLE,
    )
    sync_participants(store, poll, projects.invitees(project.id))
    return poll


def default_invitation_text(project: Project, slot: Slot | None) -> str:
    """The sentence that goes out once a date has been picked.

    Says plainly that not everybody could make it. Pretending otherwise would be
    the one dishonest sentence in an otherwise honest tool.
    """
    when = slot.label if slot else "—"
    occasion = project.occasion.rstrip(" .!?")
    if project.is_german:
        return (
            f"Wir haben einen Termin gefunden. Alle unter einen Hut zu bekommen geht nie "
            f"ganz, aber am besten passte {when}. Deswegen lade ich dich ein zu: "
            f"{occasion}. Passt das bei dir?"
        )
    return (
        f"We found a date. Getting everybody together is never quite possible, but "
        f"{when} suited most people. So I would like to invite you to: {occasion}. "
        "Does that work for you?"
    )


def invitation_round(
    store: Store,
    projects: ProjectStore,
    project: Project,
    *,
    text: str | None = None,
    create: bool = True,
) -> Poll | None:
    """The "we found a date" round. One per project, created when it is sent."""
    existing = projects.round_ids(project.id, RoundKind.INVITATION)
    if existing:
        poll = store.get_poll(existing[0])
        if text and text.strip() and text.strip() != poll.question:
            assert_question_allowed(text)
            store.set_poll_question(poll.id, text.strip())
            poll = store.get_poll(poll.id)
        return poll
    if not create:
        return None

    decision = projects.decision(project.id)
    slot = None
    if decision:
        slot = next((s for s in projects.slots(project.id) if s.id == decision.slot_id), None)
    question = (text or "").strip() or default_invitation_text(project, slot)
    assert_question_allowed(question)

    poll = store.create_poll(
        question=question,
        kind=PollKind.OPEN,
        organizer=project.organizer,
        language=project.language,
        region=project.region,
        locale=project.locale,
        project_id=project.id,
        round_kind=RoundKind.INVITATION,
    )
    sync_participants(store, poll, projects.invitees(project.id))
    return poll


# --------------------------------------------------------------------------
# 9. "Das würde jetzt passieren."
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Preview:
    """What a run would do — before it does anything."""

    poll: Poll
    requests: tuple[CallRequest, ...] = ()
    skipped: tuple[Participant, ...] = ()
    rejected: tuple[tuple[Participant, str], ...] = ()
    uncallable: tuple[Contact, ...] = ()

    @property
    def call_count(self) -> int:
        return len(self.requests)

    @property
    def cost_usd(self) -> float:
        return self.call_count * COST_PER_CALL_USD

    @property
    def task_text(self) -> str:
        """The order text, exactly as it would leave this machine."""
        return self.requests[0].task_text if self.requests else ""

    @property
    def serial_duration(self) -> str:
        return format_duration(estimate_seconds(self.call_count, concurrency=1))

    @property
    def parallel_duration(self) -> str:
        return format_duration(
            estimate_seconds(self.call_count, concurrency=max(1, self.call_count))
        )


def preview(
    store: Store, projects: ProjectStore, project: Project, poll: Poll, *, retry: bool = False
) -> Preview:
    greeting, closing = wording(projects, project)
    requests, skipped, rejected = build_requests(
        poll,
        store.participants(poll.id),
        existing=store.answers(poll.id),
        retry=retry,
        opening=greeting,
        closing=closing,
        urgency=project.urgency,
    )
    return Preview(
        poll=poll,
        requests=tuple(requests),
        skipped=tuple(skipped),
        rejected=tuple(rejected),
        uncallable=tuple(uncallable(projects.invitees(project.id))),
    )


def make_transport(
    mode: str,
    *,
    project: Project,
    fixture: Fixture | None = None,
    confirmation: str = "",
    cancel: threading.Event | None = None,
    on_activity: Callable[[ActivityLine], None] | None = None,
) -> CallTransport:
    """Build the transport for a run mode. The only door to a real telephone."""
    if mode == RunMode.SCRIPT:
        if fixture is None:
            raise ValueError(
                "a scripted run needs a fixture. This project was not created from "
                "one — use a rehearsal to see the rest of the flow, or place real calls."
            )
        return FixtureTransport(fixture.outcomes)

    if mode == RunMode.REHEARSAL:
        return RehearsalTransport(seed=project.id)

    if mode != RunMode.LIVE:
        raise ValueError(f"{mode!r} does not place calls")

    # ---- from here on real telephones are involved ----
    if confirmation.strip() != LIVE_CONFIRMATION_PHRASE:
        raise LiveCallBlocked(
            f"Live calling needs the words {LIVE_CONFIRMATION_PHRASE!r}, typed out. "
            "Nothing was dialed."
        )
    from .huckepack_key import credential_override
    from .transports.calle import CalleBatchTransport

    # Whose key pays is decided here, in the one door to a real telephone:
    # ``None`` keeps the documented resolver, a value is the visitor's own key
    # in huckepack-only-host.
    return CalleBatchTransport(
        live_confirmed=True,
        credential_override=credential_override(),
        cancel=cancel,
        on_activity=on_activity,
    )


def refuse_placeholder_numbers(store: Store, poll: Poll) -> None:
    """Never dial an example number, whatever route it arrived by."""
    forbidden = placeholder_numbers()
    hits = [p for p in store.participants(poll.id) if p.phone_e164 in forbidden]
    if hits:
        listed = ", ".join(f"{p.name} ({p.phone_masked})" for p in hits)
        raise LiveCallBlocked(
            f"These are example numbers from a bundled fixture: {listed}. They are "
            "placeholders and are never dialed. Build the project from your own "
            "contacts — people who know they will be called."
        )


def run_round(
    store: Store,
    projects: ProjectStore,
    project: Project,
    poll: Poll,
    transport: CallTransport,
    *,
    concurrency: int = 1,
    cancel: threading.Event | None = None,
    on_event: Callable[..., None] | None = None,
    retry: bool = False,
) -> RunReport:
    """Place the outstanding calls of one round. Blocks until they are done.

    Blocking is correct here — the caller decides where that happens. The
    command line blocks in the foreground; the web interface runs this in a
    thread inside the server, which is what lets somebody close the browser
    without ending the round.
    """
    if transport.is_live:
        refuse_placeholder_numbers(store, poll)
    if transport.name == RehearsalTransport.name and not poll.simulated:
        # Marked before the first invented answer is written, not after: a
        # crash halfway through must not leave made-up answers in a round that
        # does not admit to being a rehearsal.
        store.set_poll_simulated(poll.id, True)
        poll = store.get_poll(poll.id)

    greeting, closing = wording(projects, project)
    if project.state == ProjectState.DRAFT:
        projects.set_state(project.id, ProjectState.ASKING)

    return run_poll(
        store,
        poll,
        transport,
        concurrency=concurrency,
        cancel=cancel,
        on_event=on_event or (lambda event, **fields: None),
        retry=retry,
        opening=greeting,
        closing=closing,
        urgency=project.urgency,
    )


# --------------------------------------------------------------------------
# 10.-11. the board: who can when, and which slot wins
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Person:
    """One person as the board shows them: name, picture, why they count."""

    ref: str
    name: str
    contact_id: str | None = None
    initials: str = "?"
    has_photo: bool = False
    status: str = ""
    """The call status, for the people who were not reached. ``NO_ANSWER`` and
    ``BUSY`` are different news and are shown as such."""


@dataclass(frozen=True)
class SlotView:
    """One candidate date with everybody's position on it."""

    slot: Slot
    can: tuple[Person, ...] = ()
    cannot: tuple[Person, ...] = ()
    unknown: tuple[Person, ...] = ()
    """Answered the call, said nothing about this slot. Never counted as a no."""

    met: tuple[str, ...] = ()
    """Which of the configured criteria this slot meets."""

    criteria_total: int = 0

    @property
    def count(self) -> int:
        return len(self.can)

    @property
    def score(self) -> int:
        return len(self.met)

    @property
    def score_label(self) -> str:
        return f"{self.score} von {self.criteria_total}"

    @property
    def perfect(self) -> bool:
        return self.criteria_total > 0 and self.score == self.criteria_total


@dataclass(frozen=True)
class Board:
    """Everything the result view needs, computed and never stored."""

    project: Project
    poll: Poll | None
    slots: tuple[SlotView, ...] = ()
    coverage: Coverage = field(default_factory=Coverage)
    uncallable: tuple[Contact, ...] = ()
    criteria: Criteria | None = None
    decision: Decision | None = None
    merge: MergeResult | None = None
    simulated: bool = False

    @property
    def unreached(self) -> tuple[ParticipantResult, ...]:
        return self.coverage.unreached + self.coverage.pending

    @property
    def best(self) -> SlotView | None:
        """The slot to suggest: most criteria met, then most people."""
        if not self.slots:
            return None
        return max(self.slots, key=lambda view: (view.score, view.count, -view.slot.position))

    @property
    def decided_slot(self) -> SlotView | None:
        if self.decision is None:
            return None
        return next(
            (view for view in self.slots if view.slot.id == self.decision.slot_id), None
        )

    @property
    def answered_count(self) -> int:
        return self.coverage.answered_count

    @property
    def total_count(self) -> int:
        return self.coverage.total + len(self.uncallable)


@dataclass(frozen=True)
class AdvisorBoard:
    """Opinion result: tendency and dissent without discarding the raw answers."""

    project: Project
    poll: Poll | None
    merge: MergeResult | None = None
    coverage: Coverage = field(default_factory=Coverage)
    uncallable: tuple[Contact, ...] = ()
    simulated: bool = False

    @property
    def answered_count(self) -> int:
        return self.coverage.answered_count

    @property
    def total_count(self) -> int:
        return self.coverage.total + len(self.uncallable)

    @property
    def unreached(self) -> tuple[ParticipantResult, ...]:
        return self.coverage.unreached + self.coverage.pending


def _labels(value: Any) -> list[str]:
    """Read a schema array field defensively — it came from outside."""
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Iterable):
        return [str(item) for item in value if str(item).strip()]
    return []


def board(store: Store, projects: ProjectStore, project: Project) -> Board:
    """Compute the whole result view from the stored answers.

    Nothing here is persisted. The four states of the product concept —
    can, cannot, not reached, not callable at all — are three readings of the
    answers plus one reading of the address book, and keeping a second copy of
    any of them is how a report starts contradicting itself.
    """
    invitees = projects.invitees(project.id)
    slots = projects.slots(project.id)
    criteria = projects.criteria(project.id)
    decision = projects.decision(project.id)
    not_callable = tuple(uncallable(invitees))

    poll_ids = projects.round_ids(project.id, RoundKind.AVAILABILITY)
    if not poll_ids:
        return Board(
            project=project,
            poll=None,
            slots=tuple(
                SlotView(slot=slot, criteria_total=criteria.configured) for slot in slots
            ),
            uncallable=not_callable,
            criteria=criteria,
            decision=decision,
        )

    poll = store.get_poll(poll_ids[0])
    participants = store.participants(poll.id)
    merged = merge_poll(poll, participants, store.answers(poll.id))
    coverage = merged.coverage

    contact_by_ref = {
        participant.ref: participant.contact_id for participant in participants
    }
    contacts = {contact.id: contact for contact in projects.contacts()}

    def person(result: ParticipantResult) -> Person:
        contact_id = contact_by_ref.get(result.ref)
        contact = contacts.get(contact_id) if contact_id else None
        return Person(
            ref=result.ref,
            name=result.name or result.ref,
            contact_id=contact_id,
            initials=contact.initials if contact else (result.name or result.ref)[:2].upper(),
            has_photo=bool(contact and contact.has_photo),
            status=result.status.value,
        )

    index = SlotIndex([slot.label for slot in slots])
    views: list[SlotView] = []
    must_have = set(criteria.must_have)

    for slot in slots:
        key = index.key(slot.label)
        can: list[Person] = []
        cannot: list[Person] = []
        unknown: list[Person] = []
        for result in coverage.answered:
            said_yes = {index.key(label) for label in _labels(result.structured.get("available_slots"))}
            said_no = {index.key(label) for label in _labels(result.structured.get("cannot"))}
            if key in said_yes:
                can.append(person(result))
            elif key in said_no:
                cannot.append(person(result))
            else:
                unknown.append(person(result))

        met: list[str] = []
        if criteria.favourite_slot_id:
            if criteria.favourite_slot_id == slot.id:
                met.append("Lieblingstermin")
        if must_have:
            can_ids = {p.contact_id for p in can}
            if must_have.issubset(can_ids):
                met.append("Pflichtpersonen dabei")
        if criteria.min_count:
            if len(can) >= criteria.min_count:
                met.append(f"mindestens {criteria.min_count} Personen")

        views.append(
            SlotView(
                slot=slot,
                can=tuple(can),
                cannot=tuple(cannot),
                unknown=tuple(unknown),
                met=tuple(met),
                criteria_total=criteria.configured,
            )
        )

    return Board(
        project=project,
        poll=poll,
        slots=tuple(views),
        coverage=coverage,
        uncallable=not_callable,
        criteria=criteria,
        decision=decision,
        merge=merged,
        simulated=bool(poll.simulated),
    )


def advisor_board(
    store: Store, projects: ProjectStore, project: Project
) -> AdvisorBoard:
    invitees = projects.invitees(project.id)
    not_callable = tuple(uncallable(invitees))
    poll_ids = projects.round_ids(project.id, RoundKind.ROUNDTABLE)
    if not poll_ids:
        return AdvisorBoard(project=project, poll=None, uncallable=not_callable)
    poll = store.get_poll(poll_ids[0])
    merged = merge_poll(poll, store.participants(poll.id), store.answers(poll.id))
    return AdvisorBoard(
        project=project,
        poll=poll,
        merge=merged,
        coverage=merged.coverage,
        uncallable=not_callable,
        simulated=bool(poll.simulated),
    )


def set_criteria(
    projects: ProjectStore,
    project: Project,
    *,
    favourite_slot_id: str | None = None,
    must_have: Sequence[str] = (),
    min_count: int | None = None,
) -> Criteria:
    return projects.set_criteria(
        project.id,
        favourite_slot_id=favourite_slot_id,
        min_count=min_count,
        must_have=must_have,
    )


# --------------------------------------------------------------------------
# 12. "Welcher Termin wird es?"
# --------------------------------------------------------------------------


def decide(projects: ProjectStore, project: Project, slot_id: str, note: str = "") -> Decision:
    valid = {slot.id for slot in projects.slots(project.id)}
    if slot_id not in valid:
        raise ValueError(f"{slot_id!r} is not a candidate date of this project")
    return projects.set_decision(project.id, slot_id, note)


# --------------------------------------------------------------------------
# seeding a demonstration
# --------------------------------------------------------------------------


def seed_from_fixture(
    store: Store, projects: ProjectStore, fixture_name: str
) -> Project:
    """Build a complete project from a bundled fixture, ready to be replayed.

    This is how the interface demonstrates itself with no account and no
    network: the contacts, the candidate dates and the scripted answers all come
    out of one JSON file that is also what the tests run against.
    """
    fixture = load_fixture(resolve_fixture(fixture_name))
    spec = fixture.poll
    language = str(spec.get("language", "de"))
    is_advisor_fixture = fixture.kind in (PollKind.OPEN, PollKind.CHOICE)

    project = create_project(
        projects,
        occasion=str(spec.get("question", fixture.name)),
        organizer=str(spec.get("organizer", "Lukas")),
        mode=ProjectMode.ROUNDTABLE if is_advisor_fixture else ProjectMode.SCHEDULE,
        date_kind=DateKind.DAY_SLOTS,
        language=language,
        region=str(spec.get("region", "DE")),
        locale=str(spec.get("locale", "de-DE")),
        fixture_name=fixture.name,
    )

    contact_ids: list[str] = []
    for name, phone, _ref in fixture.people:
        contact = projects.create_contact(name=name, phone=phone)
        contact_ids.append(contact.id)
    set_invitees(store, projects, project, contact_ids)

    if is_advisor_fixture:
        set_advisor_question(
            projects,
            project,
            str(spec.get("question", fixture.name)),
            options=[str(option) for option in spec.get("options") or []],
        )
        roundtable_round(store, projects, project)
    else:
        # The fixture's slots are already labels; keep them verbatim so the scripted
        # answers still match. A generated label would silently break every fixture.
        projects.replace_slots(
            project, [{"label": str(label), "all_day": False} for label in spec.get("slots") or []]
        )
        poll = availability_round(store, projects, project)
        if poll is not None:
            store.set_poll_window(poll.id, [slot.label for slot in projects.slots(project.id)])
            store.set_poll_question(poll.id, str(spec.get("question", question_for(project))))
    return project


def fixture_for(project: Project) -> Fixture | None:
    if not project.fixture_name:
        return None
    return load_fixture(resolve_fixture(project.fixture_name))


def api_key_present() -> bool:
    """Whether the unified resolver can authenticate a live run."""
    from .calle_credentials import CalleCredentialError, load_calle_settings

    try:
        return load_calle_settings(required=False) is not None
    except CalleCredentialError:
        return False
