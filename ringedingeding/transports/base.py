"""Transport interface.

Serial versus parallel is a property of the transport, not of the caller. That
matters because whether CALL-E runs several calls at once is **not verified**
(the docs mention concurrency controls but not the limit). So both paths exist:
the default fan-out below runs ``concurrency`` calls at a time, and a transport
that can send one batch request instead simply overrides :meth:`place_many`.

Results are *yielded as they arrive* rather than returned at the end. The runner
persists each one immediately, which is what makes Ctrl-C safe: whatever
finished is on disk, whatever did not stays ``PENDING``.
"""

from __future__ import annotations

import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Sequence

from ..models import CallStatus, Participant, Poll

__all__ = ["CallRequest", "CallOutcome", "CallTransport"]


@dataclass(frozen=True)
class CallRequest:
    """Everything one call needs — and deliberately nothing else.

    No participant history, no other participants, no poll-wide state. What is
    in here is what leaves the machine.
    """

    poll: Poll
    participant: Participant
    task_text: str
    recipient_schema: dict[str, Any]
    aggregate_schema: dict[str, Any]
    idempotency_key: str

    def payload(self, *, redact_phone: bool = True) -> dict[str, Any]:
        """The request body as it would be sent to ``POST /v1/calls``.

        With ``redact_phone=True`` (the default) this is safe to print, log and
        paste into a report — which is exactly what ``plan`` does.
        """
        phone = self.participant.phone_masked if redact_phone else self.participant.phone_e164
        return {
            "task": self.task_text,
            "recipients": [
                {
                    "phones": [phone],
                    "region": self.poll.region,
                    "locale": self.poll.locale,
                }
            ],
            "result_schema": self.aggregate_schema,
            "recipient_result_schema": self.recipient_schema,
            "metadata": {
                # Local identifiers only. No names, no numbers, no free text.
                "poll_id": self.poll.id,
                "participant_ref": self.participant.ref,
            },
        }


@dataclass(frozen=True)
class CallOutcome:
    """What came back for one call."""

    participant_id: str
    status: CallStatus
    structured: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    """Free text from the call side. Untrusted — masked before display."""

    transcript: str = ""
    """What was actually said, in ``[mm:ss] SPEAKER: Text`` form.

    Carried alongside ``structured`` rather than instead of it, because the
    voice agent interprets free answers: a measured call turned "2. Yes,
    dissatisfied." into the category *dissatisfied* on its own. Keeping only
    the interpretation would make that step unverifiable, so both travel
    together. Untrusted text — masked before display.
    """

    run_id: str | None = None
    error: str | None = None


class CallTransport:
    """Base class for anything that can place calls."""

    name: str = "abstract"
    supports_batch: bool = False
    is_live: bool = False
    """True only for transports that can dial a real telephone."""

    def place_one(self, request: CallRequest) -> CallOutcome:
        raise NotImplementedError

    def place_many(
        self,
        requests: Sequence[CallRequest],
        *,
        concurrency: int = 1,
        cancel: threading.Event | None = None,
    ) -> Iterator[CallOutcome]:
        """Place all ``requests``, yielding outcomes as they complete.

        ``concurrency=1`` keeps strict input order, which makes runs
        reproducible; anything above fans out and yields in completion order.
        A set ``cancel`` event stops *new* calls from starting. Calls already in
        flight are allowed to finish — hanging up on a person mid-sentence
        would be worse than waiting.
        """
        if concurrency <= 1:
            yield from self._place_serial(requests, cancel=cancel)
            return
        yield from self._place_parallel(requests, concurrency=concurrency, cancel=cancel)

    def _place_serial(
        self,
        requests: Sequence[CallRequest],
        *,
        cancel: threading.Event | None,
    ) -> Iterator[CallOutcome]:
        for request in requests:
            if cancel is not None and cancel.is_set():
                return
            yield self._safe_place(request)

    def _place_parallel(
        self,
        requests: Sequence[CallRequest],
        *,
        concurrency: int,
        cancel: threading.Event | None,
    ) -> Iterator[CallOutcome]:
        pending = list(requests)
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures: set[Any] = set()
            while pending or futures:
                while pending and len(futures) < concurrency:
                    if cancel is not None and cancel.is_set():
                        pending.clear()
                        break
                    futures.add(pool.submit(self._safe_place, pending.pop(0)))
                if not futures:
                    break
                done, futures = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    yield future.result()

    def _safe_place(self, request: CallRequest) -> CallOutcome:
        """Never let one failed call abort the rest of the poll."""
        try:
            return self.place_one(request)
        except Exception as error:  # noqa: BLE001 - deliberately broad
            return CallOutcome(
                participant_id=request.participant.id,
                status=CallStatus.FAILED,
                error=f"{type(error).__name__}: {error}",
            )

    def close(self) -> None:
        """Release resources. Safe to call more than once."""

    def __enter__(self) -> "CallTransport":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def as_sequence(value: Iterable[CallRequest]) -> Sequence[CallRequest]:
    return value if isinstance(value, Sequence) else tuple(value)
