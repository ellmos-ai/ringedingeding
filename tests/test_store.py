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


def test_a_poll_language_without_an_explicit_region_derives_a_matching_one(store):
    """Field finding, 2026-08-11: ``--language de`` alone used to leave
    region/locale at their own independent defaults ("US"/"en-US") — German
    prose read out with a US voice in a US region."""
    poll = store.create_poll(question="?", kind="open", organizer="L", language="de")
    assert poll.region == "DE"
    assert poll.locale == "de-DE"


def test_a_poll_region_or_locale_explicitly_set_still_wins(store):
    poll = store.create_poll(
        question="?", kind="open", organizer="L", language="de", region="CH", locale="de-CH"
    )
    assert poll.region == "CH"
    assert poll.locale == "de-CH"


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


def test_the_transcript_is_stored_alongside_the_interpretation(store):
    """The agent's reading of an answer is only checkable against the wording."""
    poll = store.create_poll(question="Q", kind="open", organizer="L")
    participant = store.add_participant(poll.id, name="Anna", phone="+15555550100")
    store.record_answer(
        Answer(
            participant_id=participant.id,
            call_status=CallStatus.COMPLETED,
            structured={"reachable": True, "refused": False, "answer": "dissatisfied"},
            transcript="[00:12] USER: synthetische Kategorie zwei",
        )
    )
    loaded = store.answers(poll.id)[participant.id]
    assert loaded.transcript == "[00:12] USER: synthetische Kategorie zwei"
    assert loaded.structured["answer"] == "dissatisfied"


def test_a_database_from_an_older_version_is_upgraded_not_rejected(tmp_path):
    """The transcript column arrived later; saved polls must keep working."""
    import sqlite3

    path = tmp_path / "old.db"
    old = sqlite3.connect(str(path))
    old.executescript(
        """
        CREATE TABLE poll (id TEXT PRIMARY KEY, question TEXT NOT NULL,
            kind TEXT NOT NULL, organizer TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'en', region TEXT NOT NULL DEFAULT 'US',
            locale TEXT NOT NULL DEFAULT 'en-US', options_json TEXT NOT NULL DEFAULT '[]',
            window_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open');
        CREATE TABLE participant (id TEXT PRIMARY KEY, poll_id TEXT NOT NULL,
            ref TEXT NOT NULL, name TEXT NOT NULL, phone_e164 TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'pending', call_run_id TEXT, attempted_at TEXT,
            UNIQUE (poll_id, ref));
        CREATE TABLE answer (participant_id TEXT PRIMARY KEY, call_status TEXT NOT NULL,
            structured_json TEXT NOT NULL DEFAULT '{}', raw_text TEXT NOT NULL DEFAULT '',
            received_at TEXT NOT NULL, run_id TEXT, error TEXT);
        INSERT INTO poll VALUES ('poll_old','Q','open','L','en','US','en-US','[]','[]','2026-01-01','open');
        INSERT INTO participant VALUES ('p_old','poll_old','anna','Anna','+15555550100','done',NULL,NULL);
        INSERT INTO answer VALUES ('p_old','COMPLETED','{}','summary','2026-01-01',NULL,NULL);
        """
    )
    old.commit()
    old.close()

    with Store(path) as upgraded:
        loaded = upgraded.answers("poll_old")["p_old"]
        assert loaded.call_status is CallStatus.COMPLETED
        assert loaded.raw_text == "summary"
        assert loaded.transcript == ""
        # and the new column is usable from here on
        upgraded.record_answer(
            Answer(
                participant_id="p_old",
                call_status=CallStatus.COMPLETED,
                transcript="[00:01] BOT: Hello.",
            )
        )
        assert upgraded.answers("poll_old")["p_old"].transcript == "[00:01] BOT: Hello."


def test_an_in_flight_status_is_not_mistaken_for_a_failure():
    assert CallStatus.parse("PREPARING") is CallStatus.PREPARING
    assert CallStatus.parse("preparing") is CallStatus.PREPARING
    assert CallStatus.PREPARING.is_terminal is False
    # known() reports "not one of ours"; parse() falls back to FAILED.
    assert CallStatus.known("something new") is None
    assert CallStatus.parse("something new") is CallStatus.FAILED
