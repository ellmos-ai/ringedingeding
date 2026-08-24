"""Waiting for a call to finish, and reporting what happens while it does.

These tests replay the timeline of the one real call that was observed
(FINDINGS.md sections 1-3, 6): the status sat on ``PREPARING`` through the
whole conversation while ``activity`` grew, and only afterwards did the status
flip and ``result.transcript`` appear.

No socket is opened here. ``_request`` is replaced and the sleeps are set to
zero, so what is under test is the decision logic, not the network.
"""

from __future__ import annotations

import pytest
from conftest import make_participant, make_poll

from ringedingeding.activity import Speaker
from ringedingeding.models import CallStatus
from ringedingeding.safety import idempotency_key
from ringedingeding.schemas import aggregate_result_schema, recipient_result_schema
from ringedingeding.transports.base import CallRequest
from ringedingeding.transports.calle import API_KEY_ENV, CalleTransport


def _request(ref="anna", phone="+15555550100"):
    poll = make_poll()
    participant = make_participant(ref, phone)
    return CallRequest(
        poll=poll,
        participant=participant,
        task_text="...",
        recipient_schema=recipient_result_schema(poll),
        aggregate_schema=aggregate_result_schema(poll),
        idempotency_key=idempotency_key(poll.id, participant.id),
    )


def _transport(monkeypatch, responses, *, seen=None):
    """A transport whose GET returns ``responses`` in order, without sleeping."""
    monkeypatch.setenv(API_KEY_ENV, "test-key")
    transport = CalleTransport(
        live_confirmed=True,
        first_poll_delay=0.0,
        poll_interval=0.0,
        on_activity=(seen.append if seen is not None else None),
    )
    queue = list(responses)
    calls = {"count": 0}

    def fake_request(method, path, *, body=None, idempotency_key=None):
        if method == "POST":
            return {"id": "call_1"}
        calls["count"] += 1
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(transport, "_request", fake_request)
    monkeypatch.setattr(transport, "_sleep", lambda seconds, deadline: None)
    return transport, calls


# A synthetic reconstruction of the measured timeline, condensed to three polls.
RINGING = {
    "status": "PREPARING",
    "transcript": None,
    "activity": ["00:00:00.000 | Call is ringing.", "00:00:04.000 | Call connected."],
}
TALKING = {
    "status": "PREPARING",
    "transcript": None,
    "activity": [
        "00:00:00.000 | Call is ringing.",
        "00:00:04.000 | Call connected.",
        "00:00:05.000 | Bot is speaking: Dies ist ein synthetischer Testdialog.",
        "00:00:06.000 | Callee said: beispielantwort",
        "00:00:07.000 | Callee said: Beispielantwort.",
    ],
}
DONE = {
    "status": "COMPLETED",
    "transcript": None,
    "activity": TALKING["activity"] + ["00:00:25.000 | Call ended."],
    "result": {"transcript": "[00:05] BOT: Dies ist ein Test.\n[00:07] USER: Hallo."},
    "recipients": [
        {
            "status": "COMPLETED",
            "structured_result": {"reachable": True, "refused": False},
            "result": {"transcript": "[00:05] BOT: Dies ist ein Test.\n[00:07] USER: Hallo."},
        }
    ],
}


# --------------------------------------------------------------------------
# the bug this file exists for
# --------------------------------------------------------------------------


def test_preparing_does_not_end_the_wait(monkeypatch):
    """PREPARING is what an ongoing conversation looks like, not a failure.

    Before this was measured, PREPARING parsed to FAILED and counted as
    terminal — so the very first poll would have abandoned every live call as
    failed while the person was still speaking, and a re-run would have dialled
    them a second time.
    """
    transport, calls = _transport(monkeypatch, [RINGING, TALKING, DONE])
    outcome = transport.place_one(_request())
    assert calls["count"] == 3
    assert outcome.status is CallStatus.COMPLETED


def test_preparing_is_not_a_failure_status():
    assert CallStatus.parse("PREPARING") is CallStatus.PREPARING
    assert CallStatus.PREPARING.is_terminal is False


def test_an_unknown_status_keeps_the_call_alive_rather_than_killing_it(monkeypatch):
    """The terminal statuses are a closed list; anything else is 'not yet'."""
    unknown = {"status": "WARMING_UP", "activity": []}
    transport, calls = _transport(monkeypatch, [unknown, unknown, DONE])
    outcome = transport.place_one(_request())
    assert calls["count"] == 3
    assert outcome.status is CallStatus.COMPLETED


def test_a_status_that_never_becomes_terminal_times_out_and_says_what_it_saw(monkeypatch):
    transport, _calls = _transport(monkeypatch, [{"status": "WARMING_UP"}])
    transport.poll_timeout = 0.0
    with pytest.raises(TimeoutError) as excinfo:
        transport.place_one(_request())
    assert "WARMING_UP" in str(excinfo.value)


def test_an_unknown_status_on_a_finished_call_is_still_a_failure():
    """known() keeps the call alive; parse() refuses to call it a success."""
    assert CallStatus.parse("WARMING_UP") is CallStatus.FAILED
    assert CallStatus.known("WARMING_UP") is None


# --------------------------------------------------------------------------
# progress comes from activity
# --------------------------------------------------------------------------


def test_the_conversation_is_reported_while_the_status_still_says_preparing(monkeypatch):
    seen = []
    transport, _calls = _transport(monkeypatch, [RINGING, TALKING, DONE], seen=seen)
    transport.place_one(_request())
    texts = [line.text for line in seen]
    assert "Call is ringing." in texts
    assert any(line.speaker is Speaker.CALLEE for line in seen)


def test_nothing_is_reported_twice_across_polls(monkeypatch):
    seen = []
    transport, _calls = _transport(monkeypatch, [RINGING, TALKING, DONE], seen=seen)
    transport.place_one(_request())
    raws = [line.raw for line in seen]
    assert len(raws) == len(set(raws))


def test_every_line_of_the_call_arrives_by_the_end(monkeypatch):
    seen = []
    transport, _calls = _transport(monkeypatch, [RINGING, TALKING, DONE], seen=seen)
    transport.place_one(_request())
    # Six entries in the final activity list, two of which are the same
    # utterance transcribed twice.
    assert [line.text for line in seen] == [
        "Call is ringing.",
        "Call connected.",
        "Dies ist ein synthetischer Testdialog.",
        "Beispielantwort.",
        "Call ended.",
    ]


def test_the_rough_version_of_an_utterance_is_never_shown(monkeypatch):
    """'hallo' is superseded by 'Hallo.' before it is ever printed."""
    seen = []
    transport, _calls = _transport(monkeypatch, [TALKING, DONE], seen=seen)
    transport.place_one(_request())
    assert "hallo" not in [line.text for line in seen]


def test_a_run_without_an_activity_sink_still_works(monkeypatch):
    transport, _calls = _transport(monkeypatch, [RINGING, DONE])
    assert transport.place_one(_request()).status is CallStatus.COMPLETED


# --------------------------------------------------------------------------
# the transcript
# --------------------------------------------------------------------------


def test_the_transcript_reaches_the_outcome(monkeypatch):
    transport, _calls = _transport(monkeypatch, [DONE])
    outcome = transport.place_one(_request())
    assert outcome.transcript.startswith("[00:05] BOT:")
    assert "Hallo." in outcome.transcript


def test_a_call_still_running_carries_no_transcript(monkeypatch):
    """Measured: the field is null until the call is over."""
    from ringedingeding.activity import extract_transcript

    assert extract_transcript(TALKING) == ""


def test_in_a_batch_the_call_level_transcript_is_not_handed_to_one_person():
    """Six people, six conversations - a shared transcript would be a mix-up."""
    from ringedingeding.transports.calle import _outcome_from

    outcome = _outcome_from(
        participant_id="p1",
        call={
            "status": "COMPLETED",
            "result": {"transcript": "[00:01] BOT: somebody else's call"},
            "recipients": [{"status": "COMPLETED"}, {"status": "COMPLETED"}],
        },
        recipient={"status": "COMPLETED"},
        run_id="call_1",
    )
    assert outcome.transcript == ""


def test_a_transcript_coming_back_from_the_call_is_masked():
    from ringedingeding.transports.calle import _outcome_from

    outcome = _outcome_from(
        participant_id="p1",
        call={},
        recipient={
            "status": "COMPLETED",
            "result": {"transcript": "[00:03] USER: Ruf mich auf +15555550100 an."},
        },
        run_id=None,
    )
    assert "5555550100" not in outcome.transcript
    assert "Ruf mich" in outcome.transcript
