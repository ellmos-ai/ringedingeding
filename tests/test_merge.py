"""The rule this whole project stands on.

If any test in this file starts failing, the tool is producing results that
quietly treat people who were never reached as people without an opinion.
"""

from __future__ import annotations

from conftest import answer, make_participant, make_poll

from ringedingeding.merge import merge_poll
from ringedingeding.models import Answer, CallStatus, PollKind

# --------------------------------------------------------------------------
# coverage: the non-negotiable part
# --------------------------------------------------------------------------


def test_unreached_are_not_counted_as_indifferent():
    poll = make_poll()
    people = [make_participant(ref) for ref in ("a", "b", "c", "d")]
    answers = {
        "p_a": answer("p_a", available_slots=["Sat 14-18"], cannot=[], reachable=True, refused=False),
        "p_b": answer("p_b", available_slots=["Sat 14-18"], cannot=[], reachable=True, refused=False),
        "p_c": Answer(participant_id="p_c", call_status=CallStatus.NO_ANSWER),
        "p_d": Answer(participant_id="p_d", call_status=CallStatus.BUSY),
    }
    merged = merge_poll(poll, people, answers)

    assert merged.coverage.answered_count == 2
    assert merged.coverage.total == 4
    assert not merged.coverage.is_complete
    assert {r.ref for r in merged.coverage.unreached} == {"c", "d"}
    # The distinct statuses survive; they are not flattened into "failed".
    assert {r.status for r in merged.coverage.unreached} == {
        CallStatus.NO_ANSWER,
        CallStatus.BUSY,
    }


def test_caveat_names_everyone_who_is_missing():
    poll = make_poll()
    people = [make_participant(ref) for ref in ("a", "b", "c")]
    answers = {
        "p_a": answer("p_a", available_slots=["Sat 14-18"], reachable=True, refused=False),
        "p_b": Answer(participant_id="p_b", call_status=CallStatus.NO_ANSWER),
        # p_c was never attempted at all
    }
    caveat = merge_poll(poll, people, answers).coverage.caveat
    assert caveat is not None
    assert "1 of 3" in caveat
    assert "B (NO_ANSWER)" in caveat
    assert "C" in caveat
    assert "not counted as indifferent" in caveat


def test_complete_coverage_has_no_caveat():
    poll = make_poll()
    people = [make_participant("a")]
    answers = {"p_a": answer("p_a", available_slots=["Sat 14-18"], reachable=True, refused=False)}
    merged = merge_poll(poll, people, answers)
    assert merged.coverage.is_complete
    assert merged.coverage.caveat is None


def test_declined_is_its_own_bucket_not_unreached():
    poll = make_poll()
    people = [make_participant("a"), make_participant("b")]
    answers = {
        "p_a": answer("p_a", available_slots=["Sat 14-18"], reachable=True, refused=False),
        "p_b": Answer(participant_id="p_b", call_status=CallStatus.DECLINED),
    }
    coverage = merge_poll(poll, people, answers).coverage
    assert [r.ref for r in coverage.refused] == ["b"]
    assert coverage.unreached == ()


def test_completed_call_with_refused_flag_counts_as_refusal():
    """A call can complete technically while the person declined to answer."""
    poll = make_poll()
    people = [make_participant("a")]
    answers = {"p_a": answer("p_a", reachable=True, refused=True)}
    coverage = merge_poll(poll, people, answers).coverage
    assert coverage.answered == ()
    assert [r.ref for r in coverage.refused] == ["a"]


def test_completed_call_with_wrong_person_counts_as_unreached():
    poll = make_poll()
    people = [make_participant("a")]
    answers = {"p_a": answer("p_a", reachable=False, refused=False)}
    coverage = merge_poll(poll, people, answers).coverage
    assert [r.ref for r in coverage.unreached] == ["a"]


def test_a_strangers_refusal_never_counts_as_this_participants_answer():
    """``reachable`` is checked before ``refused`` (models.py, 2026-08-11).

    The wrong person answered, declined to continue on their own behalf, and
    the round never confirmed it was reaching out to the right person at
    all. Before this ordering was fixed, a stranger's "no" turned into this
    participant's REFUSED — the exact misattribution the identity gate
    (schemas.py) exists to prevent.
    """
    poll = make_poll()
    people = [make_participant("a")]
    answers = {"p_a": answer("p_a", reachable=False, refused=True)}
    coverage = merge_poll(poll, people, answers).coverage
    assert [r.ref for r in coverage.unreached] == ["a"]
    assert coverage.refused == ()


def test_a_completed_call_with_no_structured_result_at_all_counts_as_unreached():
    """A missing ``reachable`` is not the same as an affirmed one.

    Audit finding (2026-08-11): ``transports/calle.py`` falls back to ``{}``
    when the API returns no ``structured_result`` at all — a transport hiccup,
    not a confirmation that the right person was reached. Silence must not
    read as "answered", the one rule this whole module exists to enforce.
    """
    poll = make_poll()
    people = [make_participant("a")]
    answers = {"p_a": Answer(participant_id="p_a", call_status=CallStatus.COMPLETED)}
    coverage = merge_poll(poll, people, answers).coverage
    assert [r.ref for r in coverage.unreached] == ["a"]
    assert coverage.answered == ()


# --------------------------------------------------------------------------
# slot polls
# --------------------------------------------------------------------------


def test_intersection_covers_only_people_who_answered():
    poll = make_poll(slots=("Sat 14-18", "Sun 10-14"))
    people = [make_participant(ref) for ref in ("a", "b", "c")]
    answers = {
        "p_a": answer(
            "p_a", reachable=True, refused=False,
            available_slots=["Sat 14-18", "Sun 10-14"], cannot=[],
        ),
        "p_b": answer(
            "p_b", reachable=True, refused=False,
            available_slots=["Sat 14-18"], cannot=["Sun 10-14"],
        ),
        "p_c": Answer(participant_id="p_c", call_status=CallStatus.NO_ANSWER),
    }
    merged = merge_poll(poll, people, answers)
    assert [row.label for row in merged.common] == ["Sat 14-18"]
    assert "2 who answered" in merged.headline


def test_silence_about_a_slot_is_unknown_not_a_no():
    """Nobody's calendar is filled in by inference."""
    poll = make_poll(slots=("Sat 14-18", "Sun 10-14"))
    people = [make_participant("a"), make_participant("b")]
    answers = {
        "p_a": answer(
            "p_a", reachable=True, refused=False,
            available_slots=["Sat 14-18"], cannot=["Sun 10-14"],
        ),
        # b only mentioned Saturday; Sunday was never established either way
        "p_b": answer("p_b", reachable=True, refused=False, available_slots=["Sat 14-18"]),
    }
    merged = merge_poll(poll, people, answers)
    sunday = next(row for row in merged.rows if row.label == "Sun 10-14")
    assert sunday.cannot == ("A",)
    assert sunday.unknown == ("B",)
    # An unknown blocks the slot from counting as "works for everyone".
    assert sunday not in merged.common

    saturday = next(row for row in merged.rows if row.label == "Sat 14-18")
    assert saturday.can == ("A", "B")
    assert saturday.unknown == ()
    assert saturday in merged.common


def test_no_common_slot_is_reported_as_such():
    poll = make_poll(slots=("Sat 14-18", "Sun 10-14"))
    people = [make_participant("a"), make_participant("b")]
    answers = {
        "p_a": answer(
            "p_a", reachable=True, refused=False,
            available_slots=["Sat 14-18"], cannot=["Sun 10-14"],
        ),
        "p_b": answer(
            "p_b", reachable=True, refused=False,
            available_slots=["Sun 10-14"], cannot=["Sat 14-18"],
        ),
    }
    merged = merge_poll(poll, people, answers)
    assert merged.common == ()
    assert "No slot works" in merged.headline


def test_open_scheduling_question_matches_on_normalised_wording():
    poll = make_poll(slots=())
    people = [make_participant("a"), make_participant("b")]
    answers = {
        "p_a": answer("p_a", reachable=True, refused=False, available_slots=["Sa 14:00 – 18:00 Uhr"]),
        "p_b": answer("p_b", reachable=True, refused=False, available_slots=["sa 14-18"]),
    }
    merged = merge_poll(poll, people, answers)
    assert len(merged.rows) == 1
    assert merged.rows[0].can == ("A", "B")


def test_no_answers_at_all_produces_no_intersection():
    poll = make_poll()
    people = [make_participant("a")]
    merged = merge_poll(poll, people, {})
    assert merged.common == ()
    assert "No answers yet" in merged.headline
    assert [r.ref for r in merged.coverage.pending] == ["a"]


# --------------------------------------------------------------------------
# choice polls
# --------------------------------------------------------------------------


def _choice_poll():
    return make_poll(kind=PollKind.CHOICE, options=("Photo book", "Voucher"), slots=())


def test_tally_counts_votes_and_names_the_voters():
    poll = _choice_poll()
    people = [make_participant(ref) for ref in ("a", "b", "c")]
    answers = {
        "p_a": answer("p_a", reachable=True, refused=False, choice="Photo book"),
        "p_b": answer("p_b", reachable=True, refused=False, choice="Photo book"),
        "p_c": answer("p_c", reachable=True, refused=False, choice="Voucher"),
    }
    merged = merge_poll(poll, people, answers)
    counts = {entry.option: entry.count for entry in merged.tally}
    assert counts == {"Photo book": 2, "Voucher": 1}
    photo = next(e for e in merged.tally if e.option == "Photo book")
    assert photo.voters == ("A", "B")
    assert not merged.is_tie


def test_abstention_is_not_a_vote_and_not_a_refusal():
    poll = _choice_poll()
    people = [make_participant("a"), make_participant("b")]
    answers = {
        "p_a": answer("p_a", reachable=True, refused=False, choice="Voucher"),
        "p_b": answer("p_b", reachable=True, refused=False, abstained=True),
    }
    merged = merge_poll(poll, people, answers)
    assert merged.abstained == ("B",)
    assert sum(entry.count for entry in merged.tally) == 1
    # An abstention still counts as *answered* - the person was reached.
    assert merged.coverage.answered_count == 2
    assert merged.coverage.is_complete


def test_answers_outside_the_options_stay_visible():
    poll = _choice_poll()
    people = [make_participant("a"), make_participant("b")]
    answers = {
        "p_a": answer("p_a", reachable=True, refused=False, choice="Voucher"),
        "p_b": answer(
            "p_b", reachable=True, refused=False,
            other_choice="Let's just go out for dinner instead",
        ),
    }
    merged = merge_poll(poll, people, answers)
    assert merged.other == (("B", "Let's just go out for dinner instead"),)
    assert sum(entry.count for entry in merged.tally) == 1


def test_choice_outside_the_enum_is_not_silently_dropped():
    """Even if the agent ignores the enum, the answer must not disappear."""
    poll = _choice_poll()
    people = [make_participant("a")]
    answers = {"p_a": answer("p_a", reachable=True, refused=False, choice="Something else")}
    merged = merge_poll(poll, people, answers)
    assert merged.other == (("A", "Something else"),)
    assert sum(entry.count for entry in merged.tally) == 0


def test_conditions_are_carried_alongside_the_count():
    poll = _choice_poll()
    people = [make_participant("a")]
    answers = {
        "p_a": answer(
            "p_a", reachable=True, refused=False,
            choice="Photo book", condition="yes, but only if it stays under 50 euros",
        )
    }
    merged = merge_poll(poll, people, answers)
    assert merged.conditions == (("A", "yes, but only if it stays under 50 euros"),)
    # The condition does not weaken the vote, it accompanies it.
    assert next(e for e in merged.tally if e.option == "Photo book").count == 1


def test_tie_is_reported_as_a_tie():
    poll = _choice_poll()
    people = [make_participant("a"), make_participant("b")]
    answers = {
        "p_a": answer("p_a", reachable=True, refused=False, choice="Photo book"),
        "p_b": answer("p_b", reachable=True, refused=False, choice="Voucher"),
    }
    merged = merge_poll(poll, people, answers)
    assert merged.is_tie
    assert "Tie" in merged.headline


def test_reached_but_unusable_answer_is_flagged():
    poll = _choice_poll()
    people = [make_participant("a")]
    answers = {"p_a": answer("p_a", reachable=True, refused=False)}
    merged = merge_poll(poll, people, answers)
    assert merged.unclear == ("A",)


# --------------------------------------------------------------------------
# open polls
# --------------------------------------------------------------------------


def test_open_answers_are_quoted_not_merged():
    poll = make_poll(kind=PollKind.OPEN, slots=())
    people = [make_participant("a"), make_participant("b")]
    answers = {
        "p_a": answer("p_a", reachable=True, refused=False, answer="Make it shorter."),
        "p_b": Answer(participant_id="p_b", call_status=CallStatus.VOICEMAIL),
    }
    merged = merge_poll(poll, people, answers)
    assert [entry.answer for entry in merged.entries] == ["Make it shorter."]
    assert [r.ref for r in merged.coverage.unreached] == ["b"]
