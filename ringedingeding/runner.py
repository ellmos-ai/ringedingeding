"""Turning a poll into calls, and calls into stored answers.

What the runner guarantees:

* every number is validated as E.164 **again**, immediately before dialing,
* a participant who already has a terminal answer is not called a second time,
* each dial intent carries a deterministic ``Idempotency-Key``,
* every outcome is written to the database as it arrives, so an interruption
  never loses what already happened,
* a cancel signal stops new calls but lets calls already in progress finish.

There is no scheduler here, no retry loop and no daemon. One invocation places
at most one attempt per participant and then exits. Repetition is the host's
job — Task Scheduler, cron, n8n — and is therefore visible to the user.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from .models import Answer, CallStatus, Participant, Poll
from .phone import InvalidPhoneNumber, normalize_e164
from .safety import idempotency_key
from .schemas import aggregate_result_schema, build_task_text, recipient_result_schema
from .store import Store, utc_now
from .transports.base import CallOutcome, CallRequest, CallTransport

__all__ = ["EventSink", "RunReport", "build_requests", "run_poll"]

EventSink = Callable[..., None]


def _noop(event: str, **fields: Any) -> None:  # pragma: no cover - default sink
    return None


@dataclass
class RunReport:
    poll: Poll
    requests: list[CallRequest] = field(default_factory=list)
    outcomes: list[CallOutcome] = field(default_factory=list)
    skipped: list[Participant] = field(default_factory=list)
    """Already answered in an earlier run, so not called again."""

    rejected: list[tuple[Participant, str]] = field(default_factory=list)
    """Failed validation and never dialed."""

    ambiguous: list[tuple[Participant, str]] = field(default_factory=list)
    """Shares a phone number with another participant due this run, so any
    answer from that number could not be told apart between them. Never
    dialed, and recorded as ``FAILED`` rather than silently mapped to either
    (measured 2026-08-22 — see FINDINGS.md, "Batch dedup by phone number")."""

    aborted: bool = False

    @property
    def placed(self) -> int:
        return len(self.outcomes)

    @property
    def not_placed(self) -> int:
        return max(0, len(self.requests) - len(self.outcomes))


def build_requests(
    poll: Poll,
    participants: Sequence[Participant],
    *,
    existing: dict[str, Answer] | None = None,
    retry: bool = False,
    include_names: bool = True,
    opening: Sequence[str] = (),
    closing: Sequence[str] = (),
    urgency: str = "",
) -> tuple[
    list[CallRequest],
    list[Participant],
    list[tuple[Participant, str]],
    list[tuple[Participant, str]],
]:
    """Prepare one :class:`CallRequest` per participant that still needs a call.

    Returns ``(requests, skipped, rejected, ambiguous)``.
    """
    answers = existing or {}
    recipient_schema = recipient_result_schema(poll)
    aggregate_schema = aggregate_result_schema(poll)

    requests: list[CallRequest] = []
    skipped: list[Participant] = []
    rejected: list[tuple[Participant, str]] = []
    ambiguous: list[tuple[Participant, str]] = []

    due: list[Participant] = []
    for participant in participants:
        answer = answers.get(participant.id)
        if answer is not None and answer.call_status is not CallStatus.PENDING and not retry:
            skipped.append(participant)
            continue
        due.append(participant)

    # Measured 2026-08-22, live (poll "Hochzeit", two participants on one
    # real number): CALL-E's batch endpoint can fold recipients that share a
    # phone number into a single physical call while still returning one
    # recipient entry per request, so the length-mismatch guard in
    # CalleBatchTransport (which only fires when the counts disagree) never
    # sees a problem — the same structured answer, the same transcript and
    # the same run_id were written for both participants. See FINDINGS.md,
    # "Batch dedup by phone number". Caught here instead, before any request
    # is even built, and for every transport, not only the batch one —
    # whether the same collapsing happens under ``--serial`` (a separate
    # ``POST /v1/calls`` per participant) is unmeasured and not assumed safe.
    sharers: dict[str, list[Participant]] = {}
    for participant in due:
        sharers.setdefault(participant.phone_e164, []).append(participant)

    for participant in due:
        try:
            # Defence in depth: validated on construction, checked again here
            # because this is the last point before a number could be dialed.
            normalize_e164(participant.phone_e164)
        except InvalidPhoneNumber as error:
            rejected.append((participant, str(error)))
            continue

        peers = [p for p in sharers[participant.phone_e164] if p.id != participant.id]
        if peers:
            other = ", ".join(p.ref for p in peers)
            ambiguous.append(
                (
                    participant,
                    f"shares this phone number with {other} in this same run; "
                    "CALL-E's own service can dedupe identical numbers within one "
                    "dispatch, so an answer from that number cannot be told apart "
                    "between them and is attributed to neither (measured "
                    "2026-08-22 — see FINDINGS.md). Give them distinct numbers, "
                    "or fold them into one participant, before calling again.",
                )
            )
            continue

        requests.append(
            CallRequest(
                poll=poll,
                participant=participant,
                task_text=build_task_text(
                    poll,
                    participant.given_name if include_names else None,
                    opening=opening,
                    closing=closing,
                    urgency=urgency,
                ),
                recipient_schema=recipient_schema,
                aggregate_schema=aggregate_schema,
                idempotency_key=idempotency_key(poll.id, participant.id),
            )
        )
    return requests, skipped, rejected, ambiguous


def run_poll(
    store: Store,
    poll: Poll,
    transport: CallTransport,
    *,
    concurrency: int = 1,
    cancel: threading.Event | None = None,
    on_event: EventSink = _noop,
    retry: bool = False,
    include_names: bool = True,
    opening: Sequence[str] = (),
    closing: Sequence[str] = (),
    urgency: str = "",
) -> RunReport:
    """Place the outstanding calls of ``poll`` and store what comes back."""
    participants = store.participants(poll.id)
    by_id = {participant.id: participant for participant in participants}
    requests, skipped, rejected, ambiguous = build_requests(
        poll,
        participants,
        existing=store.answers(poll.id),
        retry=retry,
        include_names=include_names,
        opening=opening,
        closing=closing,
        urgency=urgency,
    )
    report = RunReport(
        poll=poll, requests=requests, skipped=skipped, rejected=rejected, ambiguous=ambiguous
    )

    for participant, reason in rejected:
        store.record_answer(
            Answer(
                participant_id=participant.id,
                call_status=CallStatus.SKIPPED,
                received_at=utc_now(),
                error=reason,
            )
        )
        on_event("rejected", ref=participant.ref, reason=reason)

    for participant, reason in ambiguous:
        # FAILED, not SKIPPED: this is not "not attempted yet" (Bucket.PENDING,
        # "not called yet" in the report) but a definite "not reached, and
        # will not be retried automatically" (Bucket.UNREACHED, "NOT REACHED")
        # — the shared number will not stop being shared on its own.
        store.record_answer(
            Answer(
                participant_id=participant.id,
                call_status=CallStatus.FAILED,
                received_at=utc_now(),
                error=reason,
            )
        )
        on_event("ambiguous", ref=participant.ref, reason=reason)

    if not requests:
        on_event("nothing_to_do", skipped=len(skipped))
        return report

    on_event(
        "run_start",
        transport=transport.name,
        live=transport.is_live,
        count=len(requests),
        concurrency=concurrency,
    )

    for request in requests:
        on_event(
            "dialing" if transport.is_live else "simulating",
            ref=request.participant.ref,
            phone=request.participant.phone_masked,
        )

    for outcome in transport.place_many(requests, concurrency=concurrency, cancel=cancel):
        participant = by_id.get(outcome.participant_id)
        store.mark_attempted(outcome.participant_id, outcome.run_id)
        store.record_answer(
            Answer(
                participant_id=outcome.participant_id,
                call_status=outcome.status,
                structured=outcome.structured,
                raw_text=outcome.summary,
                # Stored, not just displayed: the agent's own categorisation of
                # a free answer is only checkable against the wording it heard.
                transcript=outcome.transcript,
                received_at=utc_now(),
                run_id=outcome.run_id,
                error=outcome.error,
            )
        )
        report.outcomes.append(outcome)
        on_event(
            "outcome",
            ref=participant.ref if participant else outcome.participant_id,
            status=outcome.status.value,
            error=outcome.error,
        )

    if cancel is not None and cancel.is_set():
        report.aborted = True
        on_event("aborted", placed=report.placed, remaining=report.not_placed)

    return report
