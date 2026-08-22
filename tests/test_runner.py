"""Orchestration: who gets called, who does not, and what happens on Ctrl-C."""

from __future__ import annotations

import threading

from ringedingeding.models import Answer, Bucket, CallStatus
from ringedingeding.runner import build_requests, run_poll
from ringedingeding.transports.base import CallOutcome, CallTransport


class RecordingTransport(CallTransport):
    """Answers everything with COMPLETED and remembers what it was asked to do."""

    name = "recording"

    def __init__(self, status: CallStatus = CallStatus.COMPLETED, structured=None):
        self.seen: list[str] = []
        self.status = status
        self.structured = structured or {"reachable": True, "refused": False}

    def place_one(self, request):
        self.seen.append(request.participant.ref)
        return CallOutcome(
            participant_id=request.participant.id,
            status=self.status,
            structured=dict(self.structured),
            run_id=f"run_{request.participant.ref}",
        )


class ExplodingTransport(CallTransport):
    name = "exploding"

    def place_one(self, request):
        raise RuntimeError("the line went dead")


def _poll_with_people(store, count=3):
    poll = store.create_poll(question="Q", kind="open", organizer="Lukas")
    for index in range(count):
        store.add_participant(poll.id, name=f"P{index}", phone=f"+155555501{index:02d}")
    return poll


def test_every_participant_is_called_once(store):
    poll = _poll_with_people(store, 3)
    transport = RecordingTransport()
    report = run_poll(store, poll, transport)
    assert len(transport.seen) == 3
    assert len(set(transport.seen)) == 3
    assert report.placed == 3
    assert len(store.answers(poll.id)) == 3


def test_already_answered_people_are_not_called_again(store):
    poll = _poll_with_people(store, 3)
    first = store.participants(poll.id)[0]
    store.record_answer(Answer(participant_id=first.id, call_status=CallStatus.NO_ANSWER))

    transport = RecordingTransport()
    report = run_poll(store, poll, transport)
    assert first.ref not in transport.seen
    assert len(transport.seen) == 2
    assert [p.ref for p in report.skipped] == [first.ref]


def test_retry_calls_them_again(store):
    poll = _poll_with_people(store, 2)
    first = store.participants(poll.id)[0]
    store.record_answer(Answer(participant_id=first.id, call_status=CallStatus.NO_ANSWER))

    transport = RecordingTransport()
    run_poll(store, poll, transport, retry=True)
    assert first.ref in transport.seen


def test_idempotency_key_is_stable_across_runs(store):
    poll = _poll_with_people(store, 2)
    people = store.participants(poll.id)
    first, _, _ = build_requests(poll, people)
    second, _, _ = build_requests(poll, people)
    assert [r.idempotency_key for r in first] == [r.idempotency_key for r in second]
    assert len({r.idempotency_key for r in first}) == 2


def test_retry_uses_a_different_idempotency_key_after_a_failed_attempt(store):
    """R20b, live incident 2026-08-22: a retry reused the first attempt's
    idempotency key with a changed request body (a goal-text edit had
    landed in between), and CALL-E answered both with HTTP 409
    idempotency_conflict instead of placing a fresh call. Once an attempt
    has actually happened (Store.mark_attempted bumps attempt_count), the
    next request for the same participant must carry a different key."""
    poll = _poll_with_people(store, 1)
    participant = store.participants(poll.id)[0]

    first_requests, _, _ = build_requests(poll, [participant])
    first_key = first_requests[0].idempotency_key

    store.record_answer(Answer(participant_id=participant.id, call_status=CallStatus.FAILED))
    store.mark_attempted(participant.id, "run_first_attempt")

    retried_participant = store.participants(poll.id)[0]
    retry_requests, _, _ = build_requests(
        poll, [retried_participant], existing=store.answers(poll.id), retry=True
    )
    assert retry_requests[0].idempotency_key != first_key


def test_a_failing_call_does_not_abort_the_poll(store):
    poll = _poll_with_people(store, 3)
    report = run_poll(store, poll, ExplodingTransport())
    assert report.placed == 3
    answers = store.answers(poll.id)
    assert all(a.call_status is CallStatus.FAILED for a in answers.values())
    assert all("the line went dead" in (a.error or "") for a in answers.values())


def test_outcomes_are_persisted_as_they_arrive(store):
    """What makes an interrupted run safe: nothing waits for the end."""
    poll = _poll_with_people(store, 3)
    seen_counts: list[int] = []

    class ObservingTransport(RecordingTransport):
        def place_one(self, request):
            seen_counts.append(len(store.answers(poll.id)))
            return super().place_one(request)

    run_poll(store, poll, ObservingTransport())
    # By the third call, the first two answers are already on disk.
    assert seen_counts == [0, 1, 2]


def test_cancel_stops_further_calls(store):
    poll = _poll_with_people(store, 5)
    cancel = threading.Event()

    class CancelAfterTwo(RecordingTransport):
        def place_one(self, request):
            outcome = super().place_one(request)
            if len(self.seen) == 2:
                cancel.set()
            return outcome

    transport = CancelAfterTwo()
    report = run_poll(store, poll, transport, cancel=cancel)
    assert len(transport.seen) == 2
    assert report.aborted
    assert report.not_placed == 3
    # The people who were never called stay callable later.
    assert len(store.answers(poll.id)) == 2


def test_parallel_run_calls_everyone_exactly_once(store):
    poll = _poll_with_people(store, 6)
    transport = RecordingTransport()
    report = run_poll(store, poll, transport, concurrency=3)
    assert sorted(transport.seen) == sorted(p.ref for p in store.participants(poll.id))
    assert report.placed == 6
    assert len(store.answers(poll.id)) == 6


def test_serial_run_keeps_input_order(store):
    poll = _poll_with_people(store, 4)
    transport = RecordingTransport()
    run_poll(store, poll, transport, concurrency=1)
    assert transport.seen == [p.ref for p in store.participants(poll.id)]


def test_names_can_be_withheld_from_the_call(store):
    poll = _poll_with_people(store, 1)
    requests, _, _ = build_requests(poll, store.participants(poll.id), include_names=False)
    assert "P0" not in requests[0].task_text


def test_request_payload_masks_the_number_by_default(store):
    poll = _poll_with_people(store, 1)
    requests, _, _ = build_requests(poll, store.participants(poll.id))
    payload = requests[0].payload()
    assert payload["recipients"][0]["phones"] == ["+15*****00"]
    # ... and carries no personal data in the metadata
    assert set(payload["metadata"]) == {"poll_id", "participant_ref"}


def test_request_payload_can_produce_the_real_number_for_dialing(store):
    poll = _poll_with_people(store, 1)
    requests, _, _ = build_requests(poll, store.participants(poll.id))
    payload = requests[0].payload(redact_phone=False)
    assert payload["recipients"][0]["phones"] == ["+15555550100"]


def test_nothing_to_do_is_not_an_error(store):
    poll = _poll_with_people(store, 1)
    transport = RecordingTransport()
    run_poll(store, poll, transport)
    report = run_poll(store, poll, RecordingTransport())
    assert report.placed == 0
    assert not report.aborted


# --------------------------------------------------------------------------
# two participants, one phone number
# --------------------------------------------------------------------------
#
# Measured live 2026-08-22 (poll "Hochzeit"): two participants sharing one
# real phone number both ended up with state=done and the SAME structured
# answer, the SAME transcript and the SAME call_run_id — one conversation
# was silently attributed to two identities. CALL-E's batch endpoint returns
# one recipient entry per request even when it has collapsed two identical
# numbers into a single physical call, so the existing length-mismatch guard
# in CalleBatchTransport ("refusing to map answers by position") never
# fires. See FINDINGS.md, "Batch dedup by phone number".
#
# R17 (2026-08-22, follow-up live retest poll_7cebbd1226 / poll_3aa3e96828):
# the original fix put the block in build_requests(), which stopped it from
# happening under *every* transport, including --serial — where a household
# sharing one landline is a legitimate case, because a separate
# ``POST /v1/calls`` per participant ties each answer to its own call_id
# regardless of what CALL-E does with the number. The block now lives only
# in CalleBatchTransport.place_many() (tests/test_calle_batch_transport.py)
# — build_requests() itself no longer knows about phone collisions at all,
# which is exactly what the tests below confirm.


def _poll_with_a_shared_number(store):
    poll = store.create_poll(question="Q", kind="open", organizer="Lukas")
    store.add_participant(poll.id, name="Lukas 2", phone="+491795310194")
    store.add_participant(poll.id, name="Lukas Friedrich", phone="+491795310194")
    store.add_participant(poll.id, name="Simon", phone="+15555550199")
    return poll


def test_build_requests_no_longer_knows_about_phone_collisions(store):
    """build_requests() builds a request for every due participant now,
    collision or not — see the batch-only guard in transports/calle.py."""
    poll = _poll_with_a_shared_number(store)
    people = store.participants(poll.id)
    requests, skipped, rejected = build_requests(poll, people)

    assert {r.participant.name for r in requests} == {"Lukas 2", "Lukas Friedrich", "Simon"}
    assert not skipped
    assert not rejected


def test_serial_style_dispatch_calls_both_participants_sharing_a_number(store):
    """R17(a): a transport that dials one request at a time — what --serial
    resolves to, since CalleTransport does not override place_many() and
    therefore uses this exact base-class fan-out — must dial *both*
    colliding participants normally: two separate calls, two separate
    run_ids, two separate answers. Nobody is silently skipped."""
    poll = _poll_with_a_shared_number(store)
    people = {p.name: p for p in store.participants(poll.id)}
    transport = RecordingTransport()
    report = run_poll(store, poll, transport)

    assert sorted(transport.seen) == sorted(p.ref for p in people.values())
    assert report.placed == 3

    answers = store.answers(poll.id)
    run_ids = {a.run_id for a in answers.values()}
    assert len(run_ids) == 3, "no two participants may share a run_id"
    for participant in people.values():
        answer = answers[participant.id]
        assert answer.call_status is CallStatus.COMPLETED
        assert answer.run_id == f"run_{participant.ref}"
        assert answer.bucket is Bucket.ANSWERED


def test_retry_re_attempts_a_participant_left_failed_by_a_collision(store):
    """R17(c): --retry must not be a dead end after a collision-block.

    Before R17, build_requests() excluded a colliding participant
    unconditionally, so a second run reported "nothing to do" even with
    --retry, and the FAILED collision answer never got a chance to be
    replaced. This reproduces the state a CalleBatchTransport collision
    block leaves behind (FAILED, no run_id, a "shares this phone number"
    reason) and confirms retry=True makes run_poll dispatch that
    participant again, with a fresh answer overwriting the stale one.
    """
    poll = _poll_with_a_shared_number(store)
    lukas2 = next(p for p in store.participants(poll.id) if p.name == "Lukas 2")
    store.record_answer(
        Answer(
            participant_id=lukas2.id,
            call_status=CallStatus.FAILED,
            error=(
                "shares this phone number with lukas-friedrich within this same "
                "batch dispatch; ... place this run with --serial instead."
            ),
        )
    )

    # Without --retry: correctly left alone - this was never the bug.
    transport = RecordingTransport()
    report = run_poll(store, poll, transport)
    assert lukas2.ref not in transport.seen
    assert lukas2.ref in [p.ref for p in report.skipped]
    stale = store.answers(poll.id)[lukas2.id]
    assert stale.call_status is CallStatus.FAILED

    # With --retry: genuinely attempted again, not silently left FAILED.
    transport = RecordingTransport()
    report = run_poll(store, poll, transport, retry=True)
    assert lukas2.ref in transport.seen
    assert report.placed == 3

    fresh = store.answers(poll.id)[lukas2.id]
    assert fresh.call_status is CallStatus.COMPLETED
    assert fresh.run_id == f"run_{lukas2.ref}"
