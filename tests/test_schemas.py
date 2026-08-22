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


def test_identity_question_is_marked_critical_and_never_skip():
    """R18 (RT-4c live finding, 2026-08-22): a live call skipped the identity
    question entirely even though it already stood textually in the goal --
    the same lesson as hungrycall's E38 (an instruction present in the text
    was skipped live regardless). The instruction is now explicitly ordered,
    marked CRITICAL, and carries an explicit "never skip" clause, instead of
    reading as one "first ask ..." instruction among several."""
    text = build_task_text(make_poll(organizer="Lukas"), "Anna")
    identity_step = text.split("2.", 1)[1].split("3.", 1)[0]
    assert "CRITICAL" in identity_step
    assert "before anything else" in identity_step
    assert "Never skip this question" in identity_step

    poll = make_poll(language="de", locale="de-DE", region="DE")
    text_de = build_task_text(poll, "Anna")
    identity_step_de = text_de.split("2.", 1)[1].split("3.", 1)[0]
    assert "KRITISCH" in identity_step_de
    assert "Überspringe diese Frage nie" in identity_step_de


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
# "not a good moment" callback offer — R19, live user question 2026-08-22
# --------------------------------------------------------------------------


def test_a_bad_moment_gets_offered_a_callback_time_once():
    """R19: step 2's identity-mismatch sub-case already asked for a callback
    time; step 3 (the right person is reached, but it does not suit them
    right now) did not. It now does, once -- and the honest "no automatic
    callback" disclosure from before this change stays in place unchanged.
    """
    text = build_task_text(make_poll(organizer="Lukas"), "Anna")
    moment_step = " ".join(text.split("3.", 1)[1].split("4.", 1)[0].split())
    assert "ask once for a good time to call back" in moment_step
    assert "callback_requested" in moment_step
    assert "will not call back automatically" in moment_step


def test_a_bad_moment_callback_offer_is_german_for_german_polls():
    poll = make_poll(language="de", locale="de-DE", region="DE")
    text = build_task_text(poll, "Anna")
    moment_step = " ".join(text.split("3.", 1)[1].split("4.", 1)[0].split())
    assert "frage einmal nach einem guten" in moment_step
    assert "callback_requested" in moment_step
    assert "nicht automatisch erneut anrufst" in moment_step
    assert "ask once for a good time to call back" not in text


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


# --------------------------------------------------------------------------
# correction call — R21, user idea 2026-08-22
# --------------------------------------------------------------------------


def test_correction_call_asks_identity_first_verbatim():
    text = build_task_text(
        make_poll(organizer="Lukas"),
        "Ben",
        is_correction=True,
        previous_structured={"reachable": False, "refused": False, "answer": "Pizza"},
    )
    identity_step = text.split("2.", 1)[1].split("3.", 1)[0]
    assert '"I already called once before. Am I speaking with Ben?"' in identity_step
    assert "CRITICAL" in identity_step
    assert "Never skip this question" in identity_step


def test_correction_call_confirms_previous_answer_only_after_identity():
    """Privacy order (R21) as a test, not just as prose: the previous answer
    must be textually impossible to reach before the identity question --
    whoever picked up on the first, unconfirmed call must never learn what
    somebody else may have said."""
    text = build_task_text(
        make_poll(kind=PollKind.CHOICE, options=("Grill", "Pizza"), organizer="Lukas"),
        "Ben",
        is_correction=True,
        previous_structured={"reachable": False, "refused": False, "choice": "Pizza"},
    )
    identity_index = text.index("Am I speaking with Ben?")
    answer_index = text.index("you said Pizza")
    assert identity_index < answer_index
    assert "Never mention what was said on the earlier call before identity is confirmed" in text


def test_correction_call_reads_back_the_previous_choice_answer():
    text = build_task_text(
        make_poll(kind=PollKind.CHOICE, options=("Grill", "Pizza"), organizer="Lukas"),
        "Ben",
        is_correction=True,
        previous_structured={"reachable": False, "refused": False, "choice": "Pizza"},
    )
    assert '"I forgot to ask earlier — you said Pizza, was that your answer' in text
    assert "you do not need to ask the question below again" in text


def test_correction_call_falls_back_to_asking_fresh_without_an_extractable_answer():
    """R21 live case: an unconfirmed-identity CHOICE call can leave the
    optional 'choice' field empty even though the transcript clearly heard
    an answer (Participant B in synthetic-poll-final, R20 live incident). Nothing is
    invented from raw_text/transcript -- the call asks the question fresh
    instead of guessing at a quote."""
    text = build_task_text(
        make_poll(kind=PollKind.CHOICE, options=("Grill", "Pizza"), organizer="Lukas"),
        "Ben",
        is_correction=True,
        previous_structured={"reachable": False, "refused": False},
    )
    identity_step = text.split("2.", 1)[1].split("3.", 1)[0]
    assert "I forgot to ask earlier" not in identity_step
    assert "continue with the question below as normal" in identity_step
    assert "do not mention a previous call or a previous answer" in identity_step


def test_correction_call_falls_back_to_asking_fresh_with_no_previous_structured_at_all():
    text = build_task_text(make_poll(organizer="Lukas"), "Ben", is_correction=True)
    identity_step = text.split("2.", 1)[1].split("3.", 1)[0]
    assert "I already called once before" in identity_step
    assert "continue with the question below as normal" in identity_step


def test_correction_call_keeps_the_normal_mismatch_wording_on_a_no():
    text = build_task_text(
        make_poll(organizer="Lukas"), "Ben", is_correction=True,
        previous_structured={"reachable": False, "refused": False, "answer": "Pizza"},
    )
    identity_step = text.split("2.", 1)[1].split("3.", 1)[0]
    assert "bring Ben to the phone" in identity_step
    assert "ask for a good time to call back" in identity_step
    assert "callback_requested" in identity_step
    assert "reachable stays false" in identity_step


def test_correction_call_is_german_for_german_polls():
    poll = make_poll(
        language="de", locale="de-DE", region="DE",
        kind=PollKind.CHOICE, options=("Grillen", "Pizza"),
    )
    text = build_task_text(
        poll, "Ben", is_correction=True,
        previous_structured={"reachable": False, "refused": False, "choice": "Pizza"},
    )
    identity_step = text.split("2.", 1)[1].split("3.", 1)[0]
    assert '"Ich habe eben schon einmal angerufen. Spreche ich mit Ben?"' in identity_step
    identity_index = text.index("Spreche ich mit Ben?")
    answer_index = text.index("du sagtest Pizza")
    assert identity_index < answer_index
    assert "Am I speaking with" not in text
    assert "you said" not in text


def test_a_plain_non_correction_call_is_unaffected():
    """Regression guard: is_correction defaults to False, so every existing
    call this project already places must render exactly as before."""
    text = build_task_text(make_poll(organizer="Lukas"), "Ben")
    assert "I already called once before" not in text
    assert "I forgot to ask earlier" not in text


# --------------------------------------------------------------------------
# guard: this project's own German prompt building blocks never contain a
# substitute umlaut — 2026-08-11, checked repo-wide by the operator and
# clean at the time; this test holds that.
# --------------------------------------------------------------------------


def test_this_projects_own_german_task_text_never_contains_a_substitute_umlaut():
    from ringedingeding.umlaut_check import find_umlaut_substitutes

    for given_name in (None, "Anna"):
        for kind in PollKind:
            kind_poll = make_poll(
                language="de", locale="de-DE", region="DE",
                kind=kind, options=("A", "B"), slots=("Sat 14-18", "Sun 10-14"),
            )
            text = build_task_text(
                kind_poll,
                given_name,
                opening=("Schön, dich zu hören.",),
                closing=("Bis dann.",),
                urgency="wirklich dringend",
            )
            assert find_umlaut_substitutes(text) == []


def test_correction_call_german_text_never_contains_a_substitute_umlaut():
    """R21: the correction preamble is new German prose -- hold it to the
    same guard as every other German task text."""
    from ringedingeding.umlaut_check import find_umlaut_substitutes

    for previous_structured in (
        {"reachable": False, "refused": False, "choice": "A"},
        {"reachable": False, "refused": False},
    ):
        for kind in PollKind:
            kind_poll = make_poll(
                language="de", locale="de-DE", region="DE",
                kind=kind, options=("A", "B"), slots=("Sat 14-18", "Sun 10-14"),
            )
            text = build_task_text(
                kind_poll,
                "Anna",
                is_correction=True,
                previous_structured=previous_structured,
            )
            assert find_umlaut_substitutes(text) == []
