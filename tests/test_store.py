"""Persistence: what is written must come back unchanged."""

from __future__ import annotations

import pytest

from ringedingeding.models import Answer, CallStatus, ParticipantState, PollKind
from ringedingeding.phone import InvalidPhoneNumber
from ringedingeding.store import PollNotFound, Store


def test_poll_roundtrip(store):
    created = store.create_poll(
        question="When can you make it?",
        kind="slot",
        organizer="Lukas",
        language="de",
        region="DE",
        locale="de-DE",
        slots=["Sat 14-18", "Sun 10-14"],
    )
    loaded = store.get_poll(created.id)
    assert loaded == created
    assert loaded.kind is PollKind.SLOT
    assert loaded.slots == ("Sat 14-18", "Sun 10-14")
    assert loaded.has_window


def test_choice_poll_needs_at_least_two_distinct_options(store):
    with pytest.raises(ValueError):
        store.create_poll(question="A or B?", kind="choice", organizer="L")
    with pytest.raises(ValueError):
        store.create_poll(question="A or B?", kind="choice", organizer="L", options=["A", "A"])


def test_unknown_poll_raises(store):
    with pytest.raises(PollNotFound):
        store.get_poll("nope")


def test_participants_keep_insertion_order(store):
    poll = store.create_poll(question="Q", kind="open", organizer="L")
    for index, name in enumerate(["Anna", "Ben", "Clara"]):
        store.add_participant(poll.id, name=name, phone=f"+155555501{index:02d}")
    assert [p.name for p in store.participants(poll.id)] == ["Anna", "Ben", "Clara"]


def test_duplicate_names_get_distinct_refs(store):
    poll = store.create_poll(question="Q", kind="open", organizer="L")
    store.add_participant(poll.id, name="Anna", phone="+15555550100")
    store.add_participant(poll.id, name="Anna", phone="+15555550101")
    refs = [p.ref for p in store.participants(poll.id)]
    assert refs == ["anna", "anna2"]


def test_invalid_number_is_rejected_before_it_is_stored(store):
    poll = store.create_poll(question="Q", kind="open", organizer="L")
    with pytest.raises(InvalidPhoneNumber):
        store.add_participant(poll.id, name="Anna", phone="07700 900000")
    assert store.participants(poll.id) == []


def test_number_is_normalised_on_the_way_in(store):
    poll = store.create_poll(question="Q", kind="open", organizer="L")
    participant = store.add_participant(poll.id, name="Anna", phone="+1 555 555 0100")
    assert participant.phone_e164 == "+15555550100"
    assert store.participants(poll.id)[0].phone_e164 == "+15555550100"


def test_answers_roundtrip_and_mark_the_participant_done(store):
    poll = store.create_poll(question="Q", kind="open", organizer="L")
    participant = store.add_participant(poll.id, name="Anna", phone="+15555550100")
    store.record_answer(
        Answer(
            participant_id=participant.id,
            call_status=CallStatus.COMPLETED,
            structured={"reachable": True, "refused": False, "answer": "yes"},
            raw_text="summary",
        )
    )
    answers = store.answers(poll.id)
    assert answers[participant.id].structured["answer"] == "yes"
    assert answers[participant.id].call_status is CallStatus.COMPLETED
    assert store.participants(poll.id)[0].state is ParticipantState.DONE


def test_recording_twice_replaces_rather_than_duplicates(store):
    poll = store.create_poll(question="Q", kind="open", organizer="L")
    participant = store.add_participant(poll.id, name="Anna", phone="+15555550100")
    store.record_answer(Answer(participant_id=participant.id, call_status=CallStatus.NO_ANSWER))
    store.record_answer(
        Answer(
            participant_id=participant.id,
            call_status=CallStatus.COMPLETED,
            structured={"reachable": True, "refused": False},
        )
    )
    answers = store.answers(poll.id)
    assert len(answers) == 1
    assert answers[participant.id].call_status is CallStatus.COMPLETED


def test_clear_answers_resets_participants(store):
    poll = store.create_poll(question="Q", kind="open", organizer="L")
    participant = store.add_participant(poll.id, name="Anna", phone="+15555550100")
    store.record_answer(Answer(participant_id=participant.id, call_status=CallStatus.COMPLETED))
    assert store.clear_answers(poll.id) == 1
    assert store.answers(poll.id) == {}
    assert store.participants(poll.id)[0].state is ParticipantState.PENDING


def test_state_survives_reopening_the_file(tmp_path):
    path = tmp_path / "persist.db"
    with Store(path) as first:
        poll = first.create_poll(question="Q", kind="open", organizer="L")
        participant = first.add_participant(poll.id, name="Anna", phone="+15555550100")
        first.record_answer(
            Answer(participant_id=participant.id, call_status=CallStatus.BUSY)
        )
    with Store(path) as second:
        assert second.answers(poll.id)[participant.id].call_status is CallStatus.BUSY


def test_status_parsing_accepts_both_api_spellings():
    assert CallStatus.parse("completed") is CallStatus.COMPLETED
    assert CallStatus.parse("COMPLETED") is CallStatus.COMPLETED
    assert CallStatus.parse("CANCELLED") is CallStatus.CANCELED
    assert CallStatus.parse("no_answer") is CallStatus.NO_ANSWER
    # Anything unrecognised is a failure, never silently a success.
    assert CallStatus.parse("something new") is CallStatus.FAILED
    assert CallStatus.parse(None) is CallStatus.FAILED
