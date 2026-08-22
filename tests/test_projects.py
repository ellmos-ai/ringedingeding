"""The project layer: contacts, channels, slot labels, criteria, decision."""

from __future__ import annotations

import pytest

from ringedingeding.models import Answer, CallStatus
from ringedingeding.phone import InvalidPhoneNumber
from ringedingeding.projects import (
    ChannelKind,
    DateKind,
    ProjectStore,
    slot_label,
)


@pytest.fixture()
def projects(store):
    return ProjectStore(store)


# -- contacts ---------------------------------------------------------------


def test_contact_without_phone_is_not_callable(projects):
    contact = projects.create_contact(name="Clara Ohne")
    assert contact.callable is False
    assert contact.phone is None
    assert contact.phone_masked == "—"


def test_contact_with_phone_is_callable_and_masked(projects):
    contact = projects.create_contact(name="Anna Beispiel", phone="+15555550100")
    assert contact.callable is True
    assert contact.phone == "+15555550100"
    assert contact.phone_masked == "+15*****00"
    # The raw number never appears in the masked form.
    assert "5555550100" not in contact.phone_masked


def test_invalid_number_is_refused_before_storage(projects):
    with pytest.raises(InvalidPhoneNumber):
        projects.create_contact(name="Krumm", phone="07700 900000")
    assert projects.contacts() == []


def test_adding_a_number_later_makes_the_contact_callable(projects):
    contact = projects.create_contact(name="Erik")
    assert not contact.callable
    projects.set_channel(contact.id, ChannelKind.PHONE, "+15555550111")
    assert projects.contact(contact.id).callable


def test_email_is_stored_as_its_own_channel(projects):
    """The second channel has to be a row, not a schema change (stage 2)."""
    contact = projects.create_contact(
        name="Anna", phone="+15555550100", email="anna@example.org"
    )
    assert contact.email == "anna@example.org"
    assert {channel.kind for channel in contact.channels} == {"phone", "email"}


def test_setting_a_channel_replaces_rather_than_appends(projects):
    contact = projects.create_contact(name="Anna", phone="+15555550100")
    projects.set_channel(contact.id, ChannelKind.PHONE, "+15555550999")
    contact = projects.contact(contact.id)
    assert contact.phone == "+15555550999"
    assert len([c for c in contact.channels if c.kind == "phone"]) == 1


def test_initials_for_the_avatar(projects):
    assert projects.create_contact(name="Anna Beispiel").initials == "AB"
    assert projects.create_contact(name="Ben").initials == "BE"


def test_photo_round_trip(projects):
    contact = projects.create_contact(name="Anna", phone="+15555550100")
    assert projects.photo(contact.id) is None
    projects.set_photo(contact.id, b"\x89PNG-not-really", "image/png")
    blob, mime = projects.photo(contact.id)
    assert blob == b"\x89PNG-not-really"
    assert mime == "image/png"
    assert projects.contact(contact.id).has_photo is True


@pytest.mark.parametrize("simulated", [False, True])
def test_project_deletion_erases_private_call_data_and_scoped_text(projects, simulated):
    project = projects.create_project(occasion="Private Runde", organizer="Lukas")
    contact = projects.create_contact(name="Anna", phone="+15555550100")
    projects.set_invitees(project.id, [contact.id])
    projects.set_phrases("greeting", ["Vertrauliche Begrüßung"], scope_id=project.id)
    projects.set_questions(["Vertrauliche Frage"], scope_id=project.id)
    poll = projects.store.create_poll(
        question="Private question",
        kind="open",
        organizer="Lukas",
        project_id=project.id,
        round_kind="availability",
        simulated=simulated,
    )
    participant = projects.store.add_participant(
        poll.id,
        name="Anna",
        phone="+15555550100",
        contact_id=contact.id,
    )
    projects.store.record_answer(
        Answer(
            participant_id=participant.id,
            call_status=CallStatus.COMPLETED,
            raw_text="private raw answer",
            transcript="[00:01] USER: private transcript",
        )
    )

    projects.delete_project(project.id)

    for table in ("project", "project_invitee", "phrase", "project_question", "poll"):
        column = "scope_id" if table in {"phrase", "project_question"} else (
            "project_id" if table in {"project_invitee", "poll"} else "id"
        )
        assert projects.connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (project.id,)
        ).fetchone()[0] == 0
    assert projects.connection.execute(
        "SELECT COUNT(*) FROM participant WHERE id = ?", (participant.id,)
    ).fetchone()[0] == 0
    assert projects.connection.execute(
        "SELECT COUNT(*) FROM answer WHERE participant_id = ?", (participant.id,)
    ).fetchone()[0] == 0
    assert projects.contact(contact.id).phone == "+15555550100"


def test_contact_deletion_erases_copied_number_name_and_interview(projects):
    project = projects.create_project(occasion="Private Runde", organizer="Lukas")
    contact = projects.create_contact(name="Anna", phone="+15555550100")
    poll = projects.store.create_poll(
        question="Private question",
        kind="open",
        organizer="Lukas",
        project_id=project.id,
        round_kind="roundtable",
    )
    participant = projects.store.add_participant(
        poll.id,
        name=contact.name,
        phone=contact.phone or "",
        contact_id=contact.id,
    )
    projects.store.record_answer(
        Answer(
            participant_id=participant.id,
            call_status=CallStatus.COMPLETED,
            raw_text="private answer",
            transcript="[00:01] USER: private interview",
        )
    )

    projects.delete_contact(contact.id)

    with pytest.raises(KeyError):
        projects.contact(contact.id)
    assert projects.store.participants(poll.id) == []
    assert projects.store.answers(poll.id) == {}


# -- slot labels ------------------------------------------------------------


def test_slot_label_is_speakable_and_stable():
    label = slot_label(language="de", day_date="2026-08-08", start_time="14:00", end_time="18:00")
    assert label == "Sa 08.08. 14:00-18:00"


def test_slot_label_for_a_whole_day():
    assert slot_label(language="de", day_date="2026-08-08", all_day=True) == "Sa 08.08. ganztägig"
    assert slot_label(language="en", day_date="2026-08-08", all_day=True) == "Sat 08.08. all day"


def test_slot_label_for_a_recurring_weekday():
    """Stage 2 shape, already expressible in the stage 1 table."""
    assert slot_label(language="de", weekday=1, start_time="18:00", end_time="20:00") == (
        "jeden Di 18:00-20:00"
    )


def test_slot_label_for_a_span_of_days():
    label = slot_label(language="de", day_date="2026-08-08", end_date="2026-08-10", all_day=True)
    assert label == "Sa 08.08. – Mo 10.08. ganztägig"


# -- projects and slots -----------------------------------------------------


def test_a_project_language_without_an_explicit_region_derives_a_matching_one(projects):
    """The other direction of the 2026-08-11 field finding: an English
    project used to keep the project layer's own "DE"/"de-DE" defaults
    regardless — the web UI's ``/projects`` form never sends a region at
    all, so this was live, not just theoretical."""
    project = projects.create_project(occasion="Meeting", organizer="Lukas", language="en")
    assert project.region == "US"
    assert project.locale == "en-US"


def test_a_project_region_or_locale_explicitly_set_still_wins(projects):
    project = projects.create_project(
        occasion="Essen", organizer="Lukas", language="de", region="CH", locale="de-CH"
    )
    assert project.region == "CH"
    assert project.locale == "de-CH"


def test_unbuilt_date_kinds_are_refused_by_name(projects):
    """The concept knows six kinds; four say so instead of half-working."""
    with pytest.raises(ValueError, match="stage 2"):
        projects.create_project(occasion="X", organizer="L", date_kind=DateKind.WEEK)


def test_two_slots_that_sound_alike_are_refused(projects):
    project = projects.create_project(occasion="Essen", organizer="Lukas")
    with pytest.raises(ValueError, match="spoken identically"):
        projects.replace_slots(
            project,
            [
                {"day_date": "2026-08-08", "start_time": "14:00", "end_time": "18:00"},
                {"day_date": "2026-08-08", "start_time": "14:00", "end_time": "18:00"},
            ],
        )


def test_a_slot_that_ends_before_it_starts_is_refused(projects):
    project = projects.create_project(occasion="Essen", organizer="Lukas")
    with pytest.raises(ValueError, match="not after"):
        projects.replace_slots(
            project, [{"day_date": "2026-08-08", "start_time": "18:00", "end_time": "14:00"}]
        )


def test_times_are_normalised(projects):
    project = projects.create_project(occasion="Essen", organizer="Lukas")
    slots = projects.replace_slots(
        project, [{"day_date": "2026-08-08", "start_time": "9", "end_time": "17:5"}]
    )
    assert slots[0].start_time == "09:00"
    assert slots[0].end_time == "17:05"


# --------------------------------------------------------------------------
# chronological order, regardless of input order (R6, Nutzer-Vorgabe live 2026-08-22)
# --------------------------------------------------------------------------
#
# "JEDEN Tag einzeln abfragen ... bei zwei Zeitraeumen am selben Tag geordnet
# fragen (erst frueherer, dann spaeterer Zeitraum) — UNABHAENGIG von der
# Eingabereihenfolge in der Maske." The voice agent reads poll.slots
# in order, so this is where the order it hears has to be decided.


def test_slots_come_back_grouped_by_day_regardless_of_input_order(projects):
    project = projects.create_project(occasion="Essen", organizer="Lukas")
    slots = projects.replace_slots(
        project,
        [
            # Second day entered first, on purpose.
            {"day_date": "2026-08-09", "start_time": "10:00", "end_time": "14:00"},
            {"day_date": "2026-08-08", "start_time": "14:00", "end_time": "18:00"},
        ],
    )
    assert [s.day_date for s in slots] == ["2026-08-08", "2026-08-09"]
    assert [s.position for s in slots] == [0, 1]


def test_two_windows_on_one_day_are_ordered_earlier_first_regardless_of_input_order(
    projects,
):
    """The exact R6 scenario: the later time window was typed in first."""
    project = projects.create_project(occasion="Essen", organizer="Lukas")
    slots = projects.replace_slots(
        project,
        [
            {"day_date": "2026-08-08", "start_time": "18:00", "end_time": "21:00"},
            {"day_date": "2026-08-08", "start_time": "15:00", "end_time": "17:00"},
        ],
    )
    assert [s.start_time for s in slots] == ["15:00", "18:00"]


def test_chronological_order_is_stored_not_just_returned(projects):
    """The sort has to survive a fetch, not just the one call that built it —
    every downstream reader (voice prompt, calendar, plan preview) shares
    this one stored order."""
    project = projects.create_project(occasion="Essen", organizer="Lukas")
    projects.replace_slots(
        project,
        [
            {"day_date": "2026-08-09", "start_time": "10:00", "end_time": "14:00"},
            {"day_date": "2026-08-08", "start_time": "18:00", "end_time": "21:00"},
            {"day_date": "2026-08-08", "start_time": "15:00", "end_time": "17:00"},
        ],
    )
    refetched = projects.slots(project.id)
    assert [(s.day_date, s.start_time) for s in refetched] == [
        ("2026-08-08", "15:00"),
        ("2026-08-08", "18:00"),
        ("2026-08-09", "10:00"),
    ]


def test_whole_day_slots_are_also_ordered_by_date(projects):
    project = projects.create_project(
        occasion="Essen", organizer="Lukas", date_kind=DateKind.WHOLE_DAY
    )
    slots = projects.replace_slots(
        project,
        [
            {"day_date": "2026-08-10", "all_day": True},
            {"day_date": "2026-08-08", "all_day": True},
            {"day_date": "2026-08-09", "all_day": True},
        ],
    )
    assert [s.day_date for s in slots] == ["2026-08-08", "2026-08-09", "2026-08-10"]


# -- criteria ---------------------------------------------------------------


def test_criteria_count_only_what_was_configured(projects):
    project = projects.create_project(occasion="Essen", organizer="Lukas")
    assert projects.criteria(project.id).configured == 0
    projects.set_criteria(project.id, favourite_slot_id="slot_x")
    assert projects.criteria(project.id).configured == 1
    projects.set_criteria(project.id, favourite_slot_id="slot_x", min_count=3)
    assert projects.criteria(project.id).configured == 2


def test_decision_is_replaced_not_appended(projects):
    project = projects.create_project(occasion="Essen", organizer="Lukas")
    projects.set_decision(project.id, "slot_a")
    projects.set_decision(project.id, "slot_b")
    assert projects.decision(project.id).slot_id == "slot_b"
    assert projects.project(project.id).state == "decided"
