"""The live path.

Nothing here opens a socket. What is tested is the set of refusals that stand
between a command and a ringing telephone, plus the mapping of an API payload
onto an outcome.
"""

from __future__ import annotations

import pytest
from conftest import make_participant, make_poll

from ringedingeding.models import CallStatus
from ringedingeding.safety import LiveCallBlocked, idempotency_key
from ringedingeding.schemas import aggregate_result_schema, recipient_result_schema
from ringedingeding.transports.base import CallRequest
from ringedingeding.transports.calle import (
    API_KEY_ENV,
    CalleBatchTransport,
    CalleTransport,
    _outcome_from,
)


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


# --------------------------------------------------------------------------
# construction guards
# --------------------------------------------------------------------------


def test_live_transport_refuses_without_confirmation(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "test-key")
    with pytest.raises(LiveCallBlocked):
        CalleTransport(live_confirmed=False)


def test_truthy_is_not_enough_it_must_be_true(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "test-key")
    with pytest.raises(LiveCallBlocked):
        CalleTransport(live_confirmed=1)  # type: ignore[arg-type]


def test_live_transport_refuses_without_an_api_key(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV, raising=False)
    with pytest.raises(LiveCallBlocked) as excinfo:
        CalleTransport(live_confirmed=True)
    assert API_KEY_ENV in str(excinfo.value)


def test_a_confirmed_transport_declares_itself_live(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "test-key")
    transport = CalleTransport(live_confirmed=True)
    assert transport.is_live is True
    assert transport.supports_batch is False
    assert CalleBatchTransport(live_confirmed=True).supports_batch is True


def test_the_api_key_is_not_stored_in_a_public_attribute(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "super-secret")
    transport = CalleTransport(live_confirmed=True)
    public = {key: value for key, value in vars(transport).items() if not key.startswith("_")}
    assert "super-secret" not in repr(public)


def test_the_key_travels_only_in_the_authorization_header(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "super-secret")
    transport = CalleTransport(live_confirmed=True)
    headers = transport._headers("rdd_key")
    assert headers["Authorization"] == "Bearer super-secret"
    assert headers["Idempotency-Key"] == "rdd_key"
    others = {k: v for k, v in headers.items() if k != "Authorization"}
    assert "super-secret" not in repr(others)


# --------------------------------------------------------------------------
# batch mapping
# --------------------------------------------------------------------------


def test_batch_sends_one_request_with_every_recipient(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "test-key")
    transport = CalleBatchTransport(live_confirmed=True)
    sent: list[dict] = []

    def fake_request(method, path, *, body=None, idempotency_key=None):
        sent.append({"method": method, "path": path, "body": body, "key": idempotency_key})
        return {"id": "call_1"}

    monkeypatch.setattr(transport, "_request", fake_request)
    monkeypatch.setattr(
        transport,
        "_poll_until_terminal",
        lambda call_id: {
            "status": "completed",
            "recipients": [
                {"structured_result": {"reachable": True, "refused": False}},
                {"status": "no_answer"},
            ],
        },
    )

    requests = [_request("anna", "+15555550100"), _request("ben", "+15555550101")]
    outcomes = list(transport.place_many(requests))

    assert len(sent) == 1  # one API call for the whole poll
    assert sent[0]["path"] == "/v1/calls"
    assert sent[0]["key"]  # an idempotency key is always present
    assert [r["phones"][0] for r in sent[0]["body"]["recipients"]] == [
        "+15555550100",
        "+15555550101",
    ]
    assert [outcome.status for outcome in outcomes] == [
        CallStatus.COMPLETED,
        CallStatus.NO_ANSWER,
    ]


def test_a_length_mismatch_fails_instead_of_guessing(monkeypatch):
    """Attributing one person's answer to another is the worst failure mode."""
    monkeypatch.setenv(API_KEY_ENV, "test-key")
    transport = CalleBatchTransport(live_confirmed=True)
    monkeypatch.setattr(transport, "_request", lambda *a, **k: {"id": "call_1"})
    monkeypatch.setattr(
        transport,
        "_poll_until_terminal",
        lambda call_id: {"status": "completed", "recipients": [{"structured_result": {}}]},
    )

    requests = [_request("anna"), _request("ben", "+15555550101")]
    outcomes = list(transport.place_many(requests))
    assert [o.status for o in outcomes] == [CallStatus.FAILED, CallStatus.FAILED]
    assert all("refusing to map answers by position" in (o.error or "") for o in outcomes)


def test_a_transport_error_is_reported_per_participant(monkeypatch):
    monkeypatch.setenv(API_KEY_ENV, "test-key")
    transport = CalleBatchTransport(live_confirmed=True)

    def boom(*args, **kwargs):
        raise RuntimeError("cannot reach the server")

    monkeypatch.setattr(transport, "_request", boom)
    outcomes = list(transport.place_many([_request("anna"), _request("ben", "+15555550101")]))
    assert len(outcomes) == 2
    assert all(o.status is CallStatus.FAILED for o in outcomes)


def test_cancel_stops_the_batch_before_it_starts(monkeypatch):
    import threading

    monkeypatch.setenv(API_KEY_ENV, "test-key")
    transport = CalleBatchTransport(live_confirmed=True)
    monkeypatch.setattr(
        transport, "_request", lambda *a, **k: pytest.fail("must not dial after cancel")
    )
    cancel = threading.Event()
    cancel.set()
    assert list(transport.place_many([_request()], cancel=cancel)) == []


# --------------------------------------------------------------------------
# response mapping
# --------------------------------------------------------------------------


def test_per_recipient_status_beats_the_batch_status():
    """One person's voicemail must not turn the whole batch into a failure."""
    outcome = _outcome_from(
        participant_id="p1",
        call={"status": "completed"},
        recipient={"status": "voicemail"},
        run_id="call_1",
    )
    assert outcome.status is CallStatus.VOICEMAIL


def test_batch_status_is_used_when_the_recipient_has_none():
    outcome = _outcome_from(
        participant_id="p1",
        call={"status": "completed"},
        recipient={"structured_result": {"reachable": True}},
        run_id="call_1",
    )
    assert outcome.status is CallStatus.COMPLETED
    assert outcome.structured == {"reachable": True}


def test_camel_case_results_are_accepted_too():
    outcome = _outcome_from(
        participant_id="p1",
        call={"status": "completed"},
        recipient={"structuredResult": {"refused": True}},
        run_id=None,
    )
    assert outcome.structured == {"refused": True}


def test_summaries_coming_back_from_the_call_are_masked():
    outcome = _outcome_from(
        participant_id="p1",
        call={},
        recipient={"status": "completed", "summary": "Call back on +1 555 555 0100 please"},
        run_id=None,
    )
    assert "5555550100" not in outcome.summary
    assert "Call back on" in outcome.summary


def test_a_missing_status_is_a_failure_not_a_success():
    outcome = _outcome_from(participant_id="p1", call={}, recipient={}, run_id=None)
    assert outcome.status is CallStatus.FAILED
    assert outcome.error is None


# --------------------------------------------------------------------------
# voicemail detection — measured 2026-08-11, relayed by the operator
# (FINDINGS.md section 9). CALL-E reports a mailbox pickup as a plain
# "completed" call; status alone cannot tell it apart from a real
# conversation, so the transcript is read.
# --------------------------------------------------------------------------


def _mailbox_call() -> dict:
    """The measured payload, trimmed to what the mapping actually reads."""
    return {
        "status": "completed",
        "task_completed": True,
        "failure_code": None,
        "failure_message": None,
        "evidence": [
            "Die Ansage der Mailbox bat darum, nach dem Signalton eine "
            "Nachricht zu hinterlassen."
        ],
        "recipients": [
            {
                "status": "completed",
                "attempts": [
                    {
                        "status": "completed",
                        "transcript_turns": [
                            {
                                "offset_seconds": 0,
                                "speaker": "bot",
                                "text": "Hello, this is an automated assistant.",
                            },
                            {
                                "offset_seconds": 4,
                                "speaker": "user",
                                "text": (
                                    "Die angerufene Person ist nicht erreichbar. "
                                    "bitte hinterlassen sie eine nachricht nach "
                                    "dem signalton"
                                ),
                            },
                        ],
                    }
                ],
            }
        ],
    }


def test_a_mailbox_pickup_is_reported_as_voicemail_not_completed():
    call = _mailbox_call()
    outcome = _outcome_from(
        participant_id="p1", call=call, recipient=call["recipients"][0], run_id="call_1"
    )
    assert outcome.status is CallStatus.VOICEMAIL
    assert "signalton" in outcome.transcript.lower()


def test_a_strong_voicemail_phrase_need_not_be_in_the_opening_turn():
    """'signalton' decides it on its own, wherever in the call it is said —
    unlike the ambiguous phrases below, no real participant says this."""
    recipient = {
        "status": "completed",
        "attempts": [
            {
                "transcript_turns": [
                    {"offset_seconds": 0, "speaker": "bot", "text": "Hello?"},
                    {"offset_seconds": 2, "speaker": "user", "text": "Hallo?"},
                    {"offset_seconds": 5, "speaker": "bot", "text": "Is now a good time?"},
                    {
                        "offset_seconds": 8,
                        "speaker": "user",
                        "text": "Bitte sprechen Sie nach dem Signalton.",
                    },
                ]
            }
        ],
    }
    outcome = _outcome_from(
        participant_id="p1", call={"status": "completed"}, recipient=recipient, run_id="call_1"
    )
    assert outcome.status is CallStatus.VOICEMAIL


def test_a_person_who_is_merely_unavailable_next_week_is_not_a_voicemail():
    """'nicht erreichbar' alone, in the opening turn, is not decisive.

    A real participant in a scheduling poll can say exactly this about their
    own availability. Without corroboration it must not flip a call the
    service reported as completed."""
    recipient = {
        "status": "completed",
        "structured_result": {"reachable": True, "refused": False},
        "attempts": [
            {
                "transcript_turns": [
                    {"offset_seconds": 0, "speaker": "bot", "text": "Hello, is now a good time?"},
                    {
                        "offset_seconds": 3,
                        "speaker": "user",
                        "text": "Ich bin naechste Woche nicht erreichbar, sonst gerne.",
                    },
                ]
            }
        ],
    }
    outcome = _outcome_from(
        participant_id="p1",
        call={"status": "completed", "evidence": []},
        recipient=recipient,
        run_id="call_1",
    )
    assert outcome.status is CallStatus.COMPLETED


def test_an_ambiguous_phrase_outside_the_opening_turn_is_never_enough():
    """The same phrase, said later, is not even looked at — only the opening
    turn is checked for the ambiguous patterns."""
    recipient = {
        "status": "completed",
        "attempts": [
            {
                "transcript_turns": [
                    {"offset_seconds": 0, "speaker": "bot", "text": "Hello, is now a good time?"},
                    {"offset_seconds": 3, "speaker": "user", "text": "Yes, go ahead."},
                    {"offset_seconds": 20, "speaker": "user", "text": "I might not be reachable next week though."},
                ]
            }
        ],
    }
    outcome = _outcome_from(
        participant_id="p1",
        call={"status": "completed", "evidence": ["voicemail system"]},
        recipient=recipient,
        run_id="call_1",
    )
    assert outcome.status is CallStatus.COMPLETED


def test_a_weak_voicemail_phrase_is_confirmed_by_the_agents_own_evidence():
    """'leave a message' alone in the opening turn is ambiguous; the agent's
    own evidence text can corroborate it."""
    recipient = {
        "status": "completed",
        "attempts": [
            {
                "transcript_turns": [
                    {"offset_seconds": 0, "speaker": "bot", "text": "Hello, this is a test call."},
                    {"offset_seconds": 5, "speaker": "user", "text": "Please just leave a message for me."},
                ]
            }
        ],
    }
    outcome = _outcome_from(
        participant_id="p1",
        call={
            "status": "completed",
            "evidence": ["The call reached a voicemail system before any human spoke."],
        },
        recipient=recipient,
        run_id="call_1",
    )
    assert outcome.status is CallStatus.VOICEMAIL


def test_a_human_answer_is_never_mistaken_for_a_mailbox():
    recipient = {
        "status": "completed",
        "structured_result": {"reachable": True, "refused": False, "answer": "Sure, sounds good."},
        "attempts": [
            {
                "transcript_turns": [
                    {"offset_seconds": 0, "speaker": "bot", "text": "Hello, is now a good time?"},
                    {"offset_seconds": 2, "speaker": "user", "text": "Hallo?"},
                    {"offset_seconds": 6, "speaker": "user", "text": "Sure, sounds good."},
                ]
            }
        ],
    }
    outcome = _outcome_from(
        participant_id="p1",
        call={"status": "completed", "evidence": []},
        recipient=recipient,
        run_id="call_1",
    )
    assert outcome.status is CallStatus.COMPLETED


def test_the_voicemail_check_only_applies_to_a_completed_status():
    """A call already reported as something else is never second-guessed by
    the transcript — only COMPLETED is ambiguous enough to need this."""
    recipient = {
        "status": "no_answer",
        "attempts": [
            {
                "transcript_turns": [
                    {"offset_seconds": 0, "speaker": "user", "text": "This is a voicemail box."}
                ]
            }
        ],
    }
    outcome = _outcome_from(
        participant_id="p1", call={"status": "no_answer"}, recipient=recipient, run_id="call_1"
    )
    assert outcome.status is CallStatus.NO_ANSWER


# --------------------------------------------------------------------------
# DECLINED recovered from a generic FAILED — measured 2026-08-11, relayed by
# the operator (FINDINGS.md section 9).
# --------------------------------------------------------------------------


def test_a_generic_failed_status_is_recovered_via_the_failure_message():
    call = {
        "status": "failed",
        "failure_code": "call_failed",
        "failure_message": "calling task status=DECLINED (Hangup by: user)",
        "task_completed": False,
        "recipients": [
            {"status": "failed", "attempts": [{"status": "failed", "transcript_turns": []}]}
        ],
    }
    outcome = _outcome_from(
        participant_id="p1", call=call, recipient=call["recipients"][0], run_id="call_1"
    )
    assert outcome.status is CallStatus.DECLINED
    assert outcome.error is None  # a valid outcome, not a technical failure


def test_recipient_level_failure_message_wins_over_call_level():
    outcome = _outcome_from(
        participant_id="p1",
        call={"status": "failed", "failure_message": "calling task status=BUSY"},
        recipient={
            "status": "failed",
            "failure_message": "calling task status=DECLINED (Hangup by: user)",
        },
        run_id=None,
    )
    assert outcome.status is CallStatus.DECLINED


def test_an_unrecognised_failure_message_keeps_failed_but_is_not_lost():
    """An unknown token must not be guessed at — but the diagnostic text is
    kept rather than silently dropped, masked like every other output."""
    outcome = _outcome_from(
        participant_id="p1",
        call={
            "status": "failed",
            "failure_message": "network error while dialing +1 555 555 0100",
        },
        recipient={},
        run_id=None,
    )
    assert outcome.status is CallStatus.FAILED
    assert outcome.error is not None
    assert "5555550100" not in outcome.error
    assert "network error while dialing" in outcome.error


def test_a_failure_without_a_message_carries_no_invented_error():
    outcome = _outcome_from(
        participant_id="p1", call={"status": "failed"}, recipient={}, run_id=None
    )
    assert outcome.status is CallStatus.FAILED
    assert outcome.error is None


def test_the_key_format_is_never_second_guessed(monkeypatch):
    """The documentation says keys start with 'calle_live_'. Real ones start
    with 'iams_live_'. So the prefix is not checked, and must not start being
    checked: rejecting a valid key is worse than passing a bad one on."""
    for key in ("iams_live_abc123", "calle_live_abc123", "anything-at-all"):
        monkeypatch.setenv(API_KEY_ENV, key)
        transport = CalleTransport(live_confirmed=True)
        assert transport._headers()["Authorization"] == f"Bearer {key}"


def test_the_base_url_can_be_overridden_because_it_is_unverified(monkeypatch):
    from ringedingeding.transports.calle import BASE_URL_ENV, DEFAULT_BASE_URL

    monkeypatch.setenv(API_KEY_ENV, "test-key")
    monkeypatch.delenv(BASE_URL_ENV, raising=False)
    assert CalleTransport(live_confirmed=True).base_url == DEFAULT_BASE_URL
    monkeypatch.setenv(BASE_URL_ENV, "https://elsewhere.example/")
    assert CalleTransport(live_confirmed=True).base_url == "https://elsewhere.example"
