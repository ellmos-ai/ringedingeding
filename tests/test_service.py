"""The flow itself — the part all three ways in share.

The four states of the product concept are the thing being tested here:
can, cannot, not reached, and not callable at all.
"""

from __future__ import annotations

import pytest

from ringedingeding import service
from ringedingeding.models import CallStatus, PollKind
from ringedingeding.projects import ProjectMode, ProjectStore, RoundKind
from ringedingeding.safety import LiveCallBlocked, SensitiveContent
from ringedingeding.transports.base import CallOutcome, CallTransport
from ringedingeding.transports.rehearsal import RehearsalTransport


@pytest.fixture()
def projects(store):
    return ProjectStore(store)


def test_create_project_derives_region_locale_through_the_wrapper(projects):
    """The web UI's ``/projects`` form goes through exactly this wrapper and
    never sends a region at all — before 2026-08-11 an English project kept
    this function's own hardcoded "DE" default regardless of language."""
    project = service.create_project(projects, occasion="Meeting", organizer="Lukas", language="en")
    assert project.region == "US"
    assert project.locale == "en-US"


def build(store, projects, *, with_uncallable: bool = True):
    """A small project: four people who can be called, one who cannot."""
    project = service.create_project(
        projects, occasion="Familienessen", organizer="Lukas", language="de"
    )
    ids = [
        projects.create_contact(name=name, phone=phone).id
        for name, phone in (
            ("Anna", "+15555550101"),
            ("Ben", "+15555550102"),
            ("Clara", "+15555550103"),
            ("David", "+15555550104"),
        )
    ]
    if with_uncallable:
        ids.append(projects.create_contact(name="Erik").id)
    specs = service.day_slot_specs(
        project,
        days=["2026-08-08", "2026-08-09"],
        default_times=[("14:00", "18:00")],
    )
    service.set_dates(store, projects, project, specs)
    service.set_invitees(store, projects, project, ids)
    return project


def answer(store, poll, ref, *, status=CallStatus.COMPLETED, **structured):
    from ringedingeding.models import Answer

    participant = next(p for p in store.participants(poll.id) if p.ref == ref)
    store.record_answer(
        Answer(participant_id=participant.id, call_status=status, structured=structured)
    )


# -- guest list and rounds --------------------------------------------------


def test_people_without_a_phone_never_become_participants(store, projects):
    project = build(store, projects)
    poll = service.availability_round(store, projects, project)
    assert {p.name for p in store.participants(poll.id)} == {"Anna", "Ben", "Clara", "David"}
    assert [c.name for c in service.uncallable(projects.invitees(project.id))] == ["Erik"]


def test_the_uncallable_still_appear_on_the_board(store, projects):
    project = build(store, projects)
    service.availability_round(store, projects, project)
    view = service.board(store, projects, project)
    assert [c.name for c in view.uncallable] == ["Erik"]
    # Five people were invited, and the board says five — the one who cannot be
    # called is missing from the calls, not from the count.
    assert view.total_count == 5


def test_adding_a_number_later_puts_the_person_back_in_the_round(store, projects):
    project = build(store, projects)
    poll = service.availability_round(store, projects, project)
    erik = next(c for c in projects.contacts() if c.name == "Erik")

    projects.set_channel(erik.id, "phone", "+15555550199")
    service.resync_contact(store, projects, erik.id)

    assert "Erik" in {p.name for p in store.participants(poll.id)}
    # And nobody else is queued for a second call.
    view = service.preview(store, projects, project, poll)
    assert [r.participant.name for r in view.requests] == ["Anna", "Ben", "Clara", "David", "Erik"]


def test_answers_already_given_are_not_called_again(store, projects):
    project = build(store, projects)
    poll = service.availability_round(store, projects, project)
    answer(store, poll, "anna", reachable=True, refused=False, available_slots=[])
    view = service.preview(store, projects, project, poll)
    assert "Anna" not in {r.participant.name for r in view.requests}
    assert [p.name for p in view.skipped] == ["Anna"]


def test_removing_someone_keeps_the_answer_they_already_gave(store, projects):
    project = build(store, projects)
    poll = service.availability_round(store, projects, project)
    answer(store, poll, "anna", reachable=True, refused=False, available_slots=[])
    remaining = [
        invitee.contact_id
        for invitee in projects.invitees(project.id)
        if invitee.name != "Ben"
    ]
    service.set_invitees(store, projects, project, remaining)
    names = {p.name for p in store.participants(poll.id)}
    assert "Ben" not in names  # no answer, so removed
    assert "Anna" in names  # answered, so kept


# -- the four states --------------------------------------------------------


def test_board_separates_can_cannot_silent_and_unreached(store, projects):
    project = build(store, projects)
    poll = service.availability_round(store, projects, project)
    first, second = [slot.label for slot in projects.slots(project.id)]

    answer(store, poll, "anna", reachable=True, refused=False,
           available_slots=[first], cannot=[second])
    answer(store, poll, "ben", reachable=True, refused=False,
           available_slots=[first])  # says nothing about the second slot
    answer(store, poll, "clara", status=CallStatus.NO_ANSWER)
    answer(store, poll, "david", status=CallStatus.BUSY)

    view = service.board(store, projects, project)
    by_label = {slot.slot.label: slot for slot in view.slots}

    assert [p.name for p in by_label[first].can] == ["Anna", "Ben"]
    assert [p.name for p in by_label[second].cannot] == ["Anna"]
    # Silence about a slot is not a no.
    assert [p.name for p in by_label[second].unknown] == ["Ben"]

    unreached = {p.name: p.status.value for p in view.unreached}
    assert unreached == {"Clara": "NO_ANSWER", "David": "BUSY"}
    assert [c.name for c in view.uncallable] == ["Erik"]


def test_a_refusal_is_neither_an_answer_nor_a_failure(store, projects):
    project = build(store, projects)
    poll = service.availability_round(store, projects, project)
    answer(store, poll, "anna", reachable=True, refused=True)
    view = service.board(store, projects, project)
    assert [p.name for p in view.coverage.refused] == ["Anna"]
    assert view.answered_count == 0
    assert "Anna" not in {p.name for p in view.unreached}


# -- criteria ---------------------------------------------------------------


def test_three_of_three_criteria(store, projects):
    project = build(store, projects)
    poll = service.availability_round(store, projects, project)
    first, second = [slot.label for slot in projects.slots(project.id)]
    for ref in ("anna", "ben", "clara"):
        answer(store, poll, ref, reachable=True, refused=False,
               available_slots=[first], cannot=[second])
    answer(store, poll, "david", reachable=True, refused=False,
           available_slots=[second], cannot=[first])

    slots = projects.slots(project.id)
    anna = next(c for c in projects.contacts() if c.name == "Anna")
    service.set_criteria(
        projects, project, favourite_slot_id=slots[0].id, must_have=[anna.id], min_count=3
    )

    view = service.board(store, projects, project)
    best = view.best
    assert best.slot.label == first
    assert best.score_label == "3 von 3"
    assert best.perfect is True
    other = next(s for s in view.slots if s.slot.label == second)
    assert other.score_label == "0 von 3"


def test_score_counts_only_configured_criteria(store, projects):
    project = build(store, projects)
    poll = service.availability_round(store, projects, project)
    first = projects.slots(project.id)[0].label
    answer(store, poll, "anna", reachable=True, refused=False, available_slots=[first])
    service.set_criteria(projects, project, favourite_slot_id=projects.slots(project.id)[0].id)
    view = service.board(store, projects, project)
    assert view.slots[0].score_label == "1 von 1"


# -- wording ----------------------------------------------------------------


def test_own_sentences_are_quoted_so_they_are_spoken_verbatim(store, projects):
    project = build(store, projects)
    service.set_wording(
        projects, project, greeting=["Schön, dass ich dich erreiche."], closing=["Bis bald!"]
    )
    poll = service.availability_round(store, projects, project)
    text = service.preview(store, projects, project, poll).task_text
    assert '"Schön, dass ich dich erreiche."' in text
    assert '"Bis bald!"' in text
    # The mandatory disclosure still comes first.
    assert text.index("automatischer Assistent") < text.index("dass ich dich erreiche")


def test_a_greeting_cannot_smuggle_in_a_refused_subject(store, projects):
    project = build(store, projects)
    with pytest.raises(SensitiveContent):
        service.set_wording(projects, project, greeting=["Es geht um deine Diagnose."])


def test_a_refused_occasion_never_reaches_a_project(projects):
    with pytest.raises(SensitiveContent):
        service.create_project(projects, occasion="Notfall: bitte sofort melden", organizer="L")
    assert projects.projects() == []


# -- run modes --------------------------------------------------------------


def test_a_rehearsal_marks_its_round_as_simulated(store, projects):
    project = build(store, projects)
    poll = service.availability_round(store, projects, project)
    transport = service.make_transport(service.RunMode.REHEARSAL, project=project)
    service.run_round(store, projects, project, poll, transport)

    assert store.get_poll(poll.id).simulated is True
    view = service.board(store, projects, project)
    assert view.simulated is True


def test_a_rehearsal_is_reproducible_and_schema_valid(store, projects):
    project = build(store, projects)
    poll = service.availability_round(store, projects, project)
    service.run_round(
        store, projects, project, poll, RehearsalTransport(seed=project.id)
    )
    first = {ref: a.structured for ref, a in _by_ref(store, poll).items()}

    store.clear_answers(poll.id)
    service.run_round(
        store, projects, project, poll, RehearsalTransport(seed=project.id)
    )
    second = {ref: a.structured for ref, a in _by_ref(store, poll).items()}
    assert first == second
    # And no answer failed schema validation on the way in.
    assert all(a.error is None for a in _by_ref(store, poll).values())


class RecordingLiveTransport(CallTransport):
    """A stand-in for the real CALL-E transport: claims to be live, so
    ``run_round`` treats it like one, but never touches a network."""

    name = "recording-live"
    is_live = True

    def __init__(self):
        self.seen: list[str] = []

    def place_one(self, request):
        self.seen.append(request.participant.ref)
        return CallOutcome(
            participant_id=request.participant.id,
            status=CallStatus.COMPLETED,
            structured={
                "reachable": True,
                "refused": False,
                "available_slots": [],
                "cannot": [],
            },
            run_id=f"live_{request.participant.ref}",
        )


def _build_with_real_numbers(store, projects):
    """Like ``build()``, but with phone numbers that are not on the bundled-
    fixture placeholder list — needed for anything that goes through a
    transport with ``is_live = True``, since ``refuse_placeholder_numbers``
    would otherwise block every one of ``build()``'s example numbers on
    purpose (a demo poll must never turn into a real call by accident)."""
    project = service.create_project(
        projects, occasion="Familienessen", organizer="Lukas", language="de"
    )
    ids = [
        projects.create_contact(name=name, phone=phone).id
        for name, phone in (
            ("Anna", "+19995550101"),
            ("Ben", "+19995550102"),
            ("Clara", "+19995550103"),
            ("David", "+19995550104"),
        )
    ]
    specs = service.day_slot_specs(
        project,
        days=["2026-08-08", "2026-08-09"],
        default_times=[("14:00", "18:00")],
    )
    service.set_dates(store, projects, project, specs)
    service.set_invitees(store, projects, project, ids)
    return project


def test_going_live_discards_a_rehearsals_answers_first(store, projects):
    """Live finding, 2026-08-22: a project that had already been rehearsed
    reused the rehearsal's poll unchanged when run for real -- every
    participant already "had an answer" (the invented one), so
    build_requests skipped all of them, nothing was ever dialed, and the
    operator saw the same old checkmarks come back instead of a fresh
    round. Going live is already gated behind the typed confirmation
    phrase (see make_transport), so by the time a transport reaches
    run_round the operator has explicitly chosen real answers over
    invented ones -- the same choice the "Erfundene Antworten verwerfen"
    button (the /reset route) makes by hand. run_round now makes that
    choice automatically."""
    project = _build_with_real_numbers(store, projects)
    poll = service.availability_round(store, projects, project)
    service.run_round(store, projects, project, poll, RehearsalTransport(seed=project.id))

    rehearsed = store.get_poll(poll.id)
    assert rehearsed.simulated is True
    assert store.answers(poll.id), "sanity: the rehearsal has to write something"

    # Fetched fresh, exactly like the real "run" request does (web/jobs.py
    # re-reads the poll from the database for every job) -- a stale
    # in-memory Poll snapshot from before the rehearsal would trivially
    # still say simulated=False and defeat the very check being tested here.
    live = RecordingLiveTransport()
    service.run_round(store, projects, project, rehearsed, live)

    refreshed = store.get_poll(poll.id)
    assert refreshed.simulated is False, "no round may keep claiming to be a rehearsal after going live"
    people = store.participants(poll.id)
    assert set(live.seen) == {p.ref for p in people}, "everybody must actually be dialed, not skipped as 'already answered'"
    live_answers = store.answers(poll.id)
    assert len(live_answers) == len(people)
    assert all((a.run_id or "").startswith("live_") for a in live_answers.values()), (
        "no invented answer from the rehearsal may survive into the live round"
    )


def test_going_live_on_a_round_that_was_never_rehearsed_is_unaffected(store, projects):
    """The new clear-on-go-live step must be a no-op for the ordinary case:
    a round that has real answers already (not simulated) keeps them."""
    project = _build_with_real_numbers(store, projects)
    poll = service.availability_round(store, projects, project)
    first_live = RecordingLiveTransport()
    service.run_round(store, projects, project, poll, first_live)
    assert store.get_poll(poll.id).simulated is False
    first_run_ids = {a.participant_id: a.run_id for a in store.answers(poll.id).values()}

    # Nobody is left PENDING, so a second live run must not re-dial anyone
    # or wipe the answers that are already real.
    second_live = RecordingLiveTransport()
    service.run_round(store, projects, project, poll, second_live)
    assert second_live.seen == []
    second_run_ids = {a.participant_id: a.run_id for a in store.answers(poll.id).values()}
    assert first_run_ids == second_run_ids


def test_a_rehearsal_produces_people_who_were_not_reached(store, projects):
    """A rehearsal where everybody answers would teach the wrong lesson."""
    project = service.create_project(projects, occasion="Test", organizer="L")
    ids = [
        projects.create_contact(name=f"Person {index}", phone=f"+1555555{index:04d}").id
        for index in range(20)
    ]
    service.set_dates(
        store,
        projects,
        project,
        service.day_slot_specs(project, days=["2026-08-08"], default_times=[("14:00", "18:00")]),
    )
    service.set_invitees(store, projects, project, ids)
    poll = service.availability_round(store, projects, project)
    service.run_round(store, projects, project, poll, RehearsalTransport(seed=project.id))

    statuses = {answer.call_status for answer in store.answers(poll.id).values()}
    assert CallStatus.COMPLETED in statuses
    assert statuses - {CallStatus.COMPLETED}, "a rehearsal must include unreached people"


def test_a_scripted_run_needs_a_fixture(store, projects):
    project = build(store, projects)
    with pytest.raises(ValueError, match="needs a fixture"):
        service.make_transport(service.RunMode.SCRIPT, project=project, fixture=None)


def test_live_needs_the_typed_phrase(store, projects):
    project = build(store, projects)
    with pytest.raises(LiveCallBlocked):
        service.make_transport(service.RunMode.LIVE, project=project, confirmation="yes please")


def test_example_numbers_are_never_dialed(store, projects):
    """A demo project must not become a real call by accident."""
    project = service.seed_from_fixture(store, projects, "family-dinner")
    poll = service.availability_round(store, projects, project)
    with pytest.raises(LiveCallBlocked, match="example numbers"):
        service.refuse_placeholder_numbers(store, poll)


@pytest.mark.parametrize("fixture_name", ["team-retro", "grandma-gift"])
def test_open_and_choice_fixtures_seed_an_advisor_round(store, projects, fixture_name):
    project = service.seed_from_fixture(store, projects, fixture_name)

    assert project.mode == ProjectMode.ROUNDTABLE
    question = service.advisor_question(projects, project)
    assert question is not None
    assert question.text

    poll = service.roundtable_round(store, projects, project)
    assert poll is not None
    assert poll.kind in (PollKind.OPEN, PollKind.CHOICE)
    assert poll.round_kind == RoundKind.ROUNDTABLE
    assert service.availability_round(store, projects, project, create=False) is None


def test_slot_fixture_keeps_its_schedule_round(store, projects):
    project = service.seed_from_fixture(store, projects, "family-dinner")

    assert project.mode == ProjectMode.SCHEDULE
    assert service.advisor_question(projects, project) is None
    poll = service.availability_round(store, projects, project)
    assert poll is not None
    assert poll.kind == PollKind.SLOT
    assert poll.round_kind == RoundKind.AVAILABILITY


# -- fixtures and the invitation --------------------------------------------


def test_a_seeded_project_replays_its_fixture(store, projects):
    project = service.seed_from_fixture(store, projects, "family-dinner")
    poll = service.availability_round(store, projects, project)
    transport = service.make_transport(
        service.RunMode.SCRIPT, project=project, fixture=service.fixture_for(project)
    )
    service.run_round(store, projects, project, poll, transport)

    view = service.board(store, projects, project)
    assert view.answered_count == 4
    assert view.total_count == 6
    assert {p.status.value for p in view.unreached} == {"NO_ANSWER", "BUSY"}
    assert view.simulated is False  # scripted is not invented
    best = max(view.slots, key=lambda slot: slot.count)
    assert best.count == 4


def test_the_invitation_says_that_not_everybody_could_make_it(store, projects):
    project = build(store, projects)
    slots = projects.slots(project.id)
    service.decide(projects, project, slots[0].id)
    text = service.default_invitation_text(project, slots[0])
    assert slots[0].label in text
    assert "nie ganz" in text

    poll = service.invitation_round(store, projects, project)
    assert poll.round_kind == "invitation"
    assert poll.id != service.availability_round(store, projects, project).id


def test_deciding_on_a_foreign_slot_is_refused(store, projects):
    project = build(store, projects)
    with pytest.raises(ValueError, match="not a candidate"):
        service.decide(projects, project, "slot_from_somewhere_else")


def test_changing_the_dates_rewrites_the_window_of_the_round(store, projects):
    """Otherwise the calendar and the spoken slots drift apart."""
    project = build(store, projects)
    poll = service.availability_round(store, projects, project)
    assert len(poll.slots) == 2

    service.set_dates(
        store,
        projects,
        project,
        service.day_slot_specs(project, days=["2026-09-01"], default_times=[("10:00", "12:00")]),
    )
    assert store.get_poll(poll.id).slots == ("Di 01.09. 10:00-12:00",)


def _by_ref(store, poll):
    refs = {p.id: p.ref for p in store.participants(poll.id)}
    return {refs[pid]: answer for pid, answer in store.answers(poll.id).items()}
