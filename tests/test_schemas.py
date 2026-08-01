"""The schema is the steering, so it gets tested like logic, not like docs."""

from __future__ import annotations

from conftest import make_poll

from ringedingeding.models import PollKind
from ringedingeding.schemas import (
    aggregate_result_schema,
    build_task_text,
    recipient_result_schema,
)
from ringedingeding.validate import validate


def test_every_kind_requires_reachable_and_refused():
    """Without these two fields the merge cannot tell 'no' from 'not reached'."""
    for kind in PollKind:
        poll = make_poll(kind=kind, options=("A", "B"), slots=("Sat 14-18",))
        schema = recipient_result_schema(poll)
        assert set(schema["required"]) == {"reachable", "refused"}
        assert schema["additionalProperties"] is False


def test_declared_window_becomes_an_enum():
    poll = make_poll(slots=("Sat 14-18", "Sun 10-14"))
    schema = recipient_result_schema(poll)
    assert schema["properties"]["available_slots"]["items"]["enum"] == ["Sat 14-18", "Sun 10-14"]
    assert schema["properties"]["cannot"]["items"]["enum"] == ["Sat 14-18", "Sun 10-14"]


def test_open_scheduling_question_has_no_enum():
    poll = make_poll(slots=())
    schema = recipient_result_schema(poll)
    assert "enum" not in schema["properties"]["available_slots"]["items"]


def test_choice_schema_offers_a_separate_field_for_other_answers():
    poll = make_poll(kind=PollKind.CHOICE, options=("Photo book", "Voucher"), slots=())
    schema = recipient_result_schema(poll)
    assert schema["properties"]["choice"]["enum"] == ["Photo book", "Voucher"]
    assert "other_choice" in schema["properties"]
    assert "abstained" in schema["properties"]


def test_realistic_answers_validate_against_their_schema():
    poll = make_poll(slots=("Sat 14-18", "Sun 10-14"))
    schema = recipient_result_schema(poll)
    good = {
        "reachable": True,
        "refused": False,
        "available_slots": ["Sat 14-18"],
        "cannot": ["Sun 10-14"],
        "note": "",
    }
    assert validate(good, schema) == []


def test_a_slot_outside_the_window_is_a_violation():
    poll = make_poll(slots=("Sat 14-18",))
    schema = recipient_result_schema(poll)
    bad = {"reachable": True, "refused": False, "available_slots": ["Whenever"]}
    violations = validate(bad, schema)
    assert violations
    assert "Whenever" in violations[0]


def test_missing_required_field_is_a_violation():
    poll = make_poll()
    violations = validate({"reachable": True}, recipient_result_schema(poll))
    assert any("refused" in violation for violation in violations)


def test_aggregate_schema_stays_thin():
    """The merge is done locally, so nothing complex is asked of the agent."""
    schema = aggregate_result_schema(make_poll())
    assert list(schema["properties"]) == ["reached_count"]


# --------------------------------------------------------------------------
# the spoken instructions
# --------------------------------------------------------------------------


def test_disclosure_comes_first_and_names_the_organizer():
    text = build_task_text(make_poll(organizer="Lukas"), "Anna")
    first_rule = text.split("1.", 1)[1].split("2.", 1)[0]
    assert "automated" in first_rule
    assert "Lukas" in first_rule
    assert "Do not wait to be asked" in first_rule


def test_german_polls_get_german_instructions():
    poll = make_poll(language="de", locale="de-DE", region="DE")
    text = build_task_text(poll, "Anna")
    assert "automatischer Assistent" in text
    assert "im Auftrag von" in text
    assert "Notruf" in text


def test_instructions_forbid_persuasion_and_advice():
    text = build_task_text(make_poll(), "Anna")
    assert "Do not persuade" in text
    assert "no medical, legal or financial advice" in text
    assert "emergency services" in text


def test_instructions_forbid_leaking_other_participants():
    text = build_task_text(make_poll(), "Anna")
    assert "Never reveal who else is being called" in text


def test_only_the_given_name_travels():
    poll = make_poll()
    text = build_task_text(poll, "Anna")
    assert "Anna" in text
    # and nothing about anybody else
    assert "Ben" not in text


def test_names_can_be_left_out_entirely():
    text = build_task_text(make_poll(), None)
    assert "You are calling" not in text


def test_window_slots_are_read_out_one_by_one():
    poll = make_poll(slots=("Sat 14-18", "Sun 10-14"))
    text = build_task_text(poll, "Anna")
    assert "Sat 14-18; Sun 10-14" in text
    assert "Do not assume a slot works just because they did not mention it" in text
