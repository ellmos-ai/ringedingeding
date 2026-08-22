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
    first, _, _, _ = build_requests(poll, people)
    second, _, _, _ = build_requests(poll, people)
    assert [r.idempotency_key for r in first] == [r.idempotency_key for r in second]
    assert len({r.idempotency_key for r in first}) == 2


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
    requests, _, _, _ = build_requests(poll, store.participants(poll.id), include_names=False)
    assert "P0" not in requests[0].task_text


def test_request_payload_masks_the_number_by_default(store):
    poll = _poll_with_people(store, 1)
    requests, _, _, _ = build_requests(poll, store.participants(poll.id))
    payload = requests[0].payload()
    assert payload["recipients"][0]["phones"] == ["+15*****00"]
    # ... and carries no personal data in the metadata
    assert set(payload["metadata"]) == {"poll_id", "participant_ref"}


def test_request_payload_can_produce_the_real_number_for_dialing(store):
    poll = _poll_with_people(store, 1)
    requests, _, _, _ = build_requests(poll, store.participants(poll.id))
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


def _poll_with_a_shared_number(store):
    poll = store.create_poll(question="Q", kind="open", organizer="Lukas")
    store.add_participant(poll.id, name="Lukas 2", phone="+491795310194")
    store.add_participant(poll.id, name="Lukas Friedrich", phone="+491795310194")
    store.add_participant(poll.id, name="Simon", phone="+15555550199")
    return poll


def test_build_requests_refuses_participants_that_share_a_phone_number(store):
    poll = _poll_with_a_shared_number(store)
    people = store.participants(poll.id)
    requests, skipped, rejected, ambiguous = build_requests(poll, people)

    # Only the participant with a number nobody else in this run has is dialed.
    assert [r.participant.name for r in requests] == ["Simon"]
    assert not skipped
    assert not rejected
    assert {p.name for p, _reason in ambiguous} == {"Lukas 2", "Lukas Friedrich"}
    # Each explanation names the peer(s) it is ambiguous against by ref, not
    # just "somebody" — the operator has to be able to fix the actual collision.
    refs_by_name = {p.name: p.ref for p in people}
    reason_by_name = {p.name: reason for p, reason in ambiguous}
    assert refs_by_name["Lukas Friedrich"] in reason_by_name["Lukas 2"]
    assert refs_by_name["Lukas 2"] in reason_by_name["Lukas Friedrich"]


def test_build_requests_does_not_flag_a_number_shared_with_an_already_answered_person(store):
    """Only participants about to be dialled *in this run* can collide.

    Somebody whose answer is already on record is not a live ambiguity —
    only one call would actually go out this time.
    """
    poll = _poll_with_a_shared_number(store)
    people = store.participants(poll.id)
    already_answered = next(p for p in people if p.name == "Lukas 2")
    store.record_answer(
        Answer(participant_id=already_answered.id, call_status=CallStatus.NO_ANSWER)
    )

    requests, skipped, _rejected, ambiguous = build_requests(
        poll, store.participants(poll.id), existing=store.answers(poll.id)
    )
    assert [p.ref for p in skipped] == [already_answered.ref]
    assert not ambiguous
    assert {r.participant.name for r in requests} == {"Lukas Friedrich", "Simon"}


def test_run_poll_never_dials_participants_sharing_a_phone_number(store):
    poll = _poll_with_a_shared_number(store)
    simon = next(p for p in store.participants(poll.id) if p.name == "Simon")
    transport = RecordingTransport()
    report = run_poll(store, poll, transport)

    assert transport.seen == [simon.ref]
    assert {p.name for p, _reason in report.ambiguous} == {"Lukas 2", "Lukas Friedrich"}


def test_run_poll_records_shared_phone_participants_as_not_reached_not_pending(store):
    """FAILED (-> Bucket.UNREACHED, "NOT REACHED"), never SKIPPED (->
    Bucket.PENDING, "not called yet") — the shared number will not stop
    being shared on its own, so this is not "not attempted yet"."""
    poll = _poll_with_a_shared_number(store)
    run_poll(store, poll, RecordingTransport())

    answers = store.answers(poll.id)
    people = {p.id: p.name for p in store.participants(poll.id)}
    for participant_id, answer in answers.items():
        if people[participant_id] == "Simon":
            assert answer.call_status is CallStatus.COMPLETED
            continue
        assert answer.call_status is CallStatus.FAILED
        assert answer.run_id is None
        assert answer.error and "shares this phone number" in answer.error
        assert answer.bucket is Bucket.UNREACHED


def test_two_participants_sharing_a_number_never_get_the_same_run_id_or_answer(store):
    """The direct regression test for the live finding: no answer is ever
    written twice under two different participant identities."""
    poll = _poll_with_a_shared_number(store)
    run_poll(store, poll, RecordingTransport())

    answers = list(store.answers(poll.id).values())
    run_ids = [a.run_id for a in answers if a.run_id is not None]
    assert len(run_ids) == len(set(run_ids)), "no two participants may share a run_id"
    structured_by_status = [a.structured for a in answers if a.call_status is CallStatus.FAILED]
    assert all(s == {} for s in structured_by_status)
