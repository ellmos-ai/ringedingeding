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
