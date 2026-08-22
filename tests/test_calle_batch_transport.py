"""CalleBatchTransport's own collision guard.

Moved here from runner.build_requests() in R17: the guard only makes sense
for a request shape where two people could land in the *same*
``POST /v1/calls`` body, which is a property of this one transport, not of
dispatch in general. See FINDINGS.md, "Batch dedup by phone number", and the
module docstring in transports/calle.py for the reasoning.

No socket is opened here. ``_request`` is replaced and the sleeps are set to
zero, the same idiom as test_polling.py.
"""

from __future__ import annotations

from conftest import make_participant, make_poll

from ringedingeding.models import CallStatus
from ringedingeding.safety import idempotency_key
from ringedingeding.schemas import aggregate_result_schema, recipient_result_schema
from ringedingeding.transports.base import CallRequest
from ringedingeding.transports.calle import CalleBatchTransport

SHARED_NUMBER = "+441632960001"


def _request(poll, ref, phone):
    participant = make_participant(ref, phone)
    return CallRequest(
        poll=poll,
        participant=participant,
        task_text="...",
        recipient_schema=recipient_result_schema(poll),
        aggregate_schema=aggregate_result_schema(poll),
        idempotency_key=idempotency_key(poll.id, participant.id),
    )


def _transport(monkeypatch, *, poll_response=None):
    """A batch transport whose network calls are replaced and recorded."""
    transport = CalleBatchTransport(
        live_confirmed=True,
        credential_override="test-key",
        first_poll_delay=0.0,
        poll_interval=0.0,
    )
    posted: list[dict] = []

    def fake_request(method, path, *, body=None, idempotency_key=None):
        if method == "POST":
            posted.append(body)
            return {"id": "call_1"}
        return poll_response

    monkeypatch.setattr(transport, "_request", fake_request)
    monkeypatch.setattr(transport, "_sleep", lambda seconds, deadline: None)
    return transport, posted


def test_two_participants_sharing_a_number_are_both_blocked_before_any_network_call(monkeypatch):
    """R17(b): batch with a collision stays blocked exactly as before — the
    direct successor of the old
    test_run_poll_never_dials_participants_sharing_a_phone_number, moved from
    the runner layer (which blocked every transport, including --serial) to
    the transport layer that now owns this check."""
    poll = make_poll()
    anna = _request(poll, "anna", SHARED_NUMBER)
    ben = _request(poll, "ben", SHARED_NUMBER)
    transport, posted = _transport(monkeypatch)

    outcomes = list(transport.place_many([anna, ben]))

    assert not posted, "a fully colliding batch must never reach the network"
    assert {o.participant_id for o in outcomes} == {anna.participant.id, ben.participant.id}
    for outcome in outcomes:
        assert outcome.status is CallStatus.FAILED
        assert outcome.run_id is None
        assert "shares this phone number" in (outcome.error or "")
    # Each explanation names the OTHER participant by ref, not just "somebody" -
    # the operator has to be able to fix the actual collision.
    by_participant = {o.participant_id: o for o in outcomes}
    assert ben.participant.ref in by_participant[anna.participant.id].error
    assert anna.participant.ref in by_participant[ben.participant.id].error


def test_a_collision_does_not_block_an_unrelated_third_participant(monkeypatch):
    """The colliding pair is excluded from the POST body; a third participant
    with a distinct number is still dispatched normally, in a (now smaller)
    batch of one."""
    poll = make_poll()
    anna = _request(poll, "anna", SHARED_NUMBER)
    ben = _request(poll, "ben", SHARED_NUMBER)
    simon = _request(poll, "simon", "+15555550199")
    done = {
        "status": "COMPLETED",
        "recipients": [
            {"status": "COMPLETED", "structured_result": {"reachable": True, "refused": False}}
        ],
    }
    transport, posted = _transport(monkeypatch, poll_response=done)

    outcomes = {o.participant_id: o for o in transport.place_many([anna, ben, simon])}

    assert len(posted) == 1, "only the non-colliding survivor reaches the network"
    assert [r["phones"] for r in posted[0]["recipients"]] == [["+15555550199"]]
    assert outcomes[anna.participant.id].status is CallStatus.FAILED
    assert outcomes[ben.participant.id].status is CallStatus.FAILED
    assert outcomes[simon.participant.id].status is CallStatus.COMPLETED
    assert outcomes[simon.participant.id].run_id == "call_1"


def test_a_batch_with_no_collision_is_unaffected(monkeypatch):
    """Regression guard: the new filtering step must not touch a batch where
    nobody shares a number with anybody else."""
    poll = make_poll()
    anna = _request(poll, "anna", "+15555550100")
    ben = _request(poll, "ben", "+15555550101")
    done = {
        "status": "COMPLETED",
        "recipients": [
            {"status": "COMPLETED", "structured_result": {"reachable": True, "refused": False}},
            {"status": "NO_ANSWER"},
        ],
    }
    transport, posted = _transport(monkeypatch, poll_response=done)

    outcomes = {o.participant_id: o for o in transport.place_many([anna, ben])}

    assert len(posted) == 1
    assert len(posted[0]["recipients"]) == 2
    assert outcomes[anna.participant.id].status is CallStatus.COMPLETED
    assert outcomes[ben.participant.id].status is CallStatus.NO_ANSWER
