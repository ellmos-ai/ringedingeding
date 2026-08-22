"""Output.

Two things must hold for every rendered surface: no raw phone number appears,
and the people who did not answer are visible rather than implied.
"""

from __future__ import annotations

import pytest
from conftest import answer, make_participant, make_poll

from ringedingeding.merge import merge_poll
from ringedingeding.models import Answer, CallStatus, PollKind
from ringedingeding.render import render_markdown, render_plan, render_result, table
from ringedingeding.runner import build_requests

RAW = "+15555550100"


def _slot_scenario():
    poll = make_poll(slots=("Sat 14-18", "Sun 10-14"))
    people = [make_participant("anna", RAW), make_participant("ben", "+15555550101")]
    answers = {
        "p_anna": answer(
            "p_anna", reachable=True, refused=False,
            available_slots=["Sat 14-18"], cannot=["Sun 10-14"],
        ),
        "p_ben": Answer(participant_id="p_ben", call_status=CallStatus.NO_ANSWER),
    }
    return merge_poll(poll, people, answers)


def test_table_renders_and_survives_empty_input():
    assert table(["A", "B"], []) == "-"
    rendered = table(["Name", "Value"], [["Anna", "1"]])
    assert "Anna" in rendered
    assert rendered.startswith("+")


def test_console_result_never_prints_a_raw_number():
    rendered = render_result(_slot_scenario())
    assert RAW not in rendered
    assert "5555550100" not in rendered
    assert "+15*****00" in rendered


def test_markdown_result_never_prints_a_raw_number():
    rendered = render_markdown(_slot_scenario())
    assert RAW not in rendered
    assert "5555550100" not in rendered


def test_plan_never_prints_a_raw_number(store):
    poll = store.create_poll(question="Q", kind="open", organizer="Lukas")
    store.add_participant(poll.id, name="Anna", phone=RAW)
    requests, _, _, _ = build_requests(poll, store.participants(poll.id))
    rendered = render_plan(poll, requests, show_payload=True)
    assert RAW not in rendered
    assert "5555550100" not in rendered


def test_plan_warns_when_region_locale_do_not_match_the_language(store):
    """Field finding, 2026-08-11: a German poll can still end up with a
    mismatched region/locale — either an explicit override, or a poll stored
    before the derivation fix landed. Either way the operator needs to see
    it on the exact screen they read it from."""
    poll = store.create_poll(
        question="Wann passt es?", kind="open", organizer="Lukas",
        language="de", region="US", locale="en-US",
    )
    requests, _, _, _ = build_requests(poll, store.participants(poll.id))
    rendered = render_plan(poll, requests)
    assert "WARNING" in rendered
    assert "de" in rendered and "US" in rendered and "en-US" in rendered


def test_plan_shows_no_warning_when_region_locale_match(store):
    poll = store.create_poll(
        question="Wann passt es?", kind="open", organizer="Lukas", language="de"
    )
    requests, _, _, _ = build_requests(poll, store.participants(poll.id))
    rendered = render_plan(poll, requests)
    assert "WARNING" not in rendered


def test_plan_shows_the_goal_text_and_the_schema(store):
    poll = store.create_poll(
        question="When can you make it?", kind="slot", organizer="Lukas", slots=["Sat 14-18"]
    )
    store.add_participant(poll.id, name="Anna", phone=RAW)
    requests, _, _, _ = build_requests(poll, store.participants(poll.id))
    rendered = render_plan(poll, requests)
    assert "nothing is dialed" in rendered
    assert "automated" in rendered  # the disclosure sentence
    assert "recipient_result_schema" in rendered
    assert "Sat 14-18" in rendered
    assert "Idempotency-Key" in rendered


def test_the_missing_people_are_shown_not_implied():
    rendered = render_result(_slot_scenario())
    assert "NOT REACHED" in rendered
    assert "NO_ANSWER" in rendered
    assert "1 of 2" in rendered
    assert "not counted as indifferent" in rendered


def test_markdown_puts_the_caveat_next_to_the_result():
    rendered = render_markdown(_slot_scenario())
    result_index = rendered.index("## Result")
    caveat_index = rendered.index("not counted as indifferent")
    table_index = rendered.index("## Who answered")
    assert result_index < caveat_index < table_index


def test_transcript_text_from_a_call_is_masked_before_display():
    """Text we did not write ourselves gets scrubbed on the way out."""
    poll = make_poll(kind=PollKind.OPEN, slots=())
    people = [make_participant("anna", RAW)]
    answers = {
        "p_anna": answer(
            "p_anna", reachable=True, refused=False,
            answer=f"Ring me on {RAW} tomorrow",
        )
    }
    merged = merge_poll(poll, people, answers)
    for rendered in (render_result(merged), render_markdown(merged)):
        assert "5555550100" not in rendered
        assert "Ring me on" in rendered


@pytest.mark.parametrize("kind", list(PollKind))
def test_every_poll_kind_renders_without_answers(kind):
    """An empty poll must produce a report, not a traceback."""
    poll = make_poll(kind=kind, options=("A", "B"), slots=("Sat 14-18",))
    merged = merge_poll(poll, [make_participant("anna", RAW)], {})
    assert render_result(merged)
    assert render_markdown(merged)


def _transcribed_scenario():
    """One answer the agent interpreted, with the wording behind it."""
    poll = make_poll(kind=PollKind.CHOICE, options=("Photo book", "Voucher"), slots=())
    people = [make_participant("anna", RAW), make_participant("ben", "+15555550101")]
    answers = {
        "p_anna": Answer(
            participant_id="p_anna",
            call_status=CallStatus.COMPLETED,
            structured={"reachable": True, "refused": False, "choice": "Photo book"},
            transcript="[00:09] BOT: Photo book or voucher?\n[00:15] USER: The book I guess.",
        ),
        "p_ben": Answer(participant_id="p_ben", call_status=CallStatus.NO_ANSWER),
    }
    return merge_poll(poll, people, answers)


def test_the_markdown_report_quotes_what_was_actually_said():
    rendered = render_markdown(_transcribed_scenario())
    assert "What was actually said" in rendered
    assert "The book I guess." in rendered
    assert "Anna (COMPLETED)" in rendered


def test_the_console_points_at_the_transcripts_without_printing_them():
    """A whole conversation per person would bury the result table."""
    rendered = render_result(_transcribed_scenario())
    assert "Transcripts available for 1 call(s): Anna" in rendered
    assert "The book I guess." not in rendered


def test_a_report_without_transcripts_has_no_empty_section():
    rendered = render_markdown(_slot_scenario())
    assert "What was actually said" not in rendered


def test_a_transcript_is_masked_in_the_report():
    poll = make_poll(kind=PollKind.OPEN, slots=())
    people = [make_participant("anna", RAW)]
    answers = {
        "p_anna": Answer(
            participant_id="p_anna",
            call_status=CallStatus.COMPLETED,
            structured={"reachable": True, "refused": False, "answer": "call me"},
            transcript=f"[00:15] USER: Call me on {RAW} instead.",
        )
    }
    rendered = render_markdown(merge_poll(poll, people, answers))
    assert "5555550100" not in rendered
    assert "Call me on" in rendered
