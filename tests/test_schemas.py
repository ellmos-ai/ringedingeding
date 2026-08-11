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


# --------------------------------------------------------------------------
# identity gate — Nutzer-Testdesign 2026-08-11
# --------------------------------------------------------------------------


def test_identity_is_confirmed_right_after_the_disclosure():
    text = build_task_text(make_poll(organizer="Lukas"), "Anna")
    identity_step = text.split("2.", 1)[1].split("3.", 1)[0]
    assert '"Am I speaking with Anna?"' in identity_step
    # ... and, symmetrically, carries no German verbatim sentence at all —
    # the seam is poll.language, not a hardcoded language (2026-08-11
    # correction: "beide Versionen müssen in Deutsch und Englisch gehen").
    assert "Spreche ich mit" not in text
    assert "Führe das gesamte Gespräch" not in text


def test_identity_question_is_german_for_german_polls():
    poll = make_poll(language="de", locale="de-DE", region="DE")
    text = build_task_text(poll, "Anna")
    assert '"Spreche ich mit Anna?"' in text
    assert "Am I speaking with" not in text


def test_unconfirmed_identity_must_never_be_recorded_as_reached():
    text = build_task_text(make_poll(), "Anna")
    identity_step = text.split("2.", 1)[1].split("3.", 1)[0]
    assert "reachable stays false" in identity_step


def test_wrong_person_is_asked_to_fetch_the_right_one_or_offer_a_callback():
    text = build_task_text(make_poll(), "Anna")
    identity_step = text.split("2.", 1)[1].split("3.", 1)[0]
    assert "bring Anna to the phone" in identity_step
    assert "ask for a good time to call back" in identity_step
    assert "callback_requested" in identity_step
    assert "without asking the actual question" in identity_step


def test_identity_check_is_skipped_honestly_without_a_name():
    """``--no-names`` withholds the name entirely — there is nothing to ask
    "am I speaking with X" about, and the task text must not pretend there
    is."""
    text = build_task_text(make_poll(), None)
    identity_step = text.split("2.", 1)[1].split("3.", 1)[0]
    assert "Am I speaking with" not in identity_step
    assert "cannot be confirmed" in identity_step


# --------------------------------------------------------------------------
# language directive — hungrycall field trial, 2026-08-11
# --------------------------------------------------------------------------


def _unquoted(text: str) -> str:
    """Everything outside quotation marks — the part actually rephrased, per
    FINDINGS.md section 4. A directive that lands *inside* quotes would be
    read aloud verbatim instead of followed."""
    return "".join(part for index, part in enumerate(text.split('"')) if index % 2 == 0)


def test_german_polls_get_an_explicit_german_only_directive():
    poll = make_poll(language="de", locale="de-DE", region="DE")
    text = build_task_text(poll, "Anna")
    assert "Führe das gesamte Gespräch auf Deutsch" in _unquoted(text)
    assert "Conduct the entire conversation" not in text


def test_english_polls_get_an_explicit_english_only_directive():
    text = build_task_text(make_poll(), "Anna")
    assert "Conduct the entire conversation in English" in _unquoted(text)
    assert "Führe das gesamte Gespräch" not in text


# --------------------------------------------------------------------------
# schema extension — optional field, never a nullable union (issue #120)
# --------------------------------------------------------------------------


def test_callback_requested_is_offered_but_never_required():
    for kind in PollKind:
        poll = make_poll(kind=kind, options=("A", "B"), slots=("Sat 14-18",))
        schema = recipient_result_schema(poll)
        assert "callback_requested" in schema["properties"]
        assert "callback_requested" not in schema["required"]
        assert set(schema["required"]) == {"reachable", "refused"}


def _nullable_unions(schema: object, path: str = "$") -> list[str]:
    """Every place a schema headed for CALL-E would be rejected for nullability.

    Regression guard for upstream issue #120 (verified 2026-08-11 via
    ``gh issue view 120``, CALLE-AI/awesome-phone-call-agents): CALL-E rejects
    the entire call-create request (``result_schema_invalid``) for a nullable
    union type anywhere in the schema (``{"type": ["string", "null"]}``), a
    bare ``"type": "null"``, or a ``null`` entry inside an ``enum``.
    """
    problems: list[str] = []
    if isinstance(schema, dict):
        type_value = schema.get("type")
        if isinstance(type_value, list) and "null" in type_value:
            problems.append(f"{path}.type is a nullable union: {type_value!r}")
        elif type_value == "null":
            problems.append(f"{path}.type is the bare null type")
        enum_value = schema.get("enum")
        if isinstance(enum_value, list) and any(item is None for item in enum_value):
            problems.append(f"{path}.enum contains a null entry")
        for key, value in schema.items():
            problems.extend(_nullable_unions(value, f"{path}.{key}"))
    elif isinstance(schema, list):
        for index, item in enumerate(schema):
            problems.extend(_nullable_unions(item, f"{path}[{index}]"))
    return problems


def test_no_schema_sent_to_calle_ever_contains_a_nullable_union():
    for kind in PollKind:
        poll = make_poll(kind=kind, options=("A", "B"), slots=("Sat 14-18",))
        for schema in (recipient_result_schema(poll), aggregate_result_schema(poll)):
            assert _nullable_unions(schema) == []
