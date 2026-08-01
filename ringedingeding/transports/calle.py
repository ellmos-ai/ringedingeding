"""Live transports — the only code in this project that can dial a telephone.

Nothing here runs during a dry run, and nothing here can be constructed by
accident: the constructor refuses unless ``live_confirmed=True`` was passed,
which the CLI only does after ``--live`` *and* a typed confirmation.

Built against the REST API (``POST /v1/calls``, ``GET /v1/calls/{id}``) with the
standard library only, so that installing this project never pulls a network
stack it does not need.

Why REST and not the MCP tools
------------------------------

Measured, not assumed (FINDINGS.md section 5): the MCP surface
(``plan_call`` / ``run_call`` / ``get_call_run``) has **no result-schema
parameter at all**. Schema-validated per-recipient answers exist only over
REST. Since this whole project is built on ``recipient_result_schema`` — the
schema is what makes the voice agent ask the right questions — the MCP path
cannot carry it and is not used.

The two surfaces are also **separate worlds**: a call started over MCP is not
retrievable via ``GET /v1/calls/{run_id}`` (measured: HTTP 404 with a valid
key). So there is no mixing them, and no fallback from one to the other.

What is measured and what is not
--------------------------------

Measured, and therefore relied upon here:

* progress comes from ``activity``, not from ``status`` — the status field sat
  on ``PREPARING`` throughout an ongoing conversation,
* the transcript lives in ``result.transcript`` as a string, not in
  ``transcript`` at the top level, which stayed ``null``,
* roughly 40 seconds pass before a telephone rings, whatever the call.

Still **not** measured, and therefore kept open rather than assumed:

* whether several calls may run in parallel. Both paths exist and the operator
  chooses; nothing here claims one is safe.
* the REST base URL. :data:`DEFAULT_BASE_URL` is what the documentation states;
  the observed calls went through the MCP endpoint, which is a different host.
  Override with ``CALLE_BASE_URL`` if it turns out to be wrong.
* the exact JSON shape of an ``activity`` entry. Only its rendered form was
  seen, so :mod:`ringedingeding.activity` parses permissively.
* whether the batch response's ``recipients`` array is in request order. There
  is no per-recipient identifier in the documented response, so if the lengths
  disagree every call in the batch is reported as ``FAILED`` instead of being
  guessed at — attributing one person's answer to another is the worst thing
  this tool could do.

No code in this module has been executed against the live API. See EVIDENCE.md.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Iterator, Sequence

from ..activity import ActivityLine, dedupe, extract_activity, extract_transcript
from ..models import CallStatus
from ..phone import mask_text
from ..safety import LiveCallBlocked
from ..timings import LEAD_SECONDS
from .base import CallOutcome, CallRequest, CallTransport

__all__ = ["CalleTransport", "CalleBatchTransport", "DEFAULT_BASE_URL", "API_KEY_ENV"]

DEFAULT_BASE_URL = "https://api.heycall-e.com"
API_KEY_ENV = "CALLE_API_KEY"
BASE_URL_ENV = "CALLE_BASE_URL"

_FIRST_POLL_DELAY = LEAD_SECONDS
"""Nothing observable happens in the first ~40 seconds; the telephone has not
even rung. Polling earlier costs requests and shows an empty list.

Nothing is missed by starting late: ``activity`` is cumulative, so the first
poll returns the ringing and connecting lines as well."""

_POLL_INTERVAL = 8.0
"""Documented guidance: every 5 to 10 seconds after the first poll."""

_DEFAULT_TIMEOUT = 900.0

ActivitySink = Callable[[ActivityLine], None]


def _ignore(_line: ActivityLine) -> None:  # pragma: no cover - default sink
    return None


class CalleTransport(CallTransport):
    """One ``POST /v1/calls`` per participant, then poll until terminal."""

    name = "calle"
    supports_batch = False
    is_live = True

    def __init__(
        self,
        *,
        live_confirmed: bool,
        api_key: str | None = None,
        base_url: str | None = None,
        request_timeout: float = 30.0,
        poll_timeout: float = _DEFAULT_TIMEOUT,
        first_poll_delay: float = _FIRST_POLL_DELAY,
        poll_interval: float = _POLL_INTERVAL,
        cancel: threading.Event | None = None,
        on_activity: ActivitySink | None = None,
    ) -> None:
        if live_confirmed is not True:
            raise LiveCallBlocked(
                "Refusing to build a live transport without explicit confirmation. "
                "This is not a configuration problem — it is the safety gate."
            )
        key = api_key or os.environ.get(API_KEY_ENV, "")
        if not key:
            raise LiveCallBlocked(
                f"No API key. Set {API_KEY_ENV} in the environment. "
                "Keys are never read from files or command line arguments."
            )
        self._api_key = key
        self.base_url = (base_url or os.environ.get(BASE_URL_ENV) or DEFAULT_BASE_URL).rstrip("/")
        self.request_timeout = request_timeout
        self.poll_timeout = poll_timeout
        self.first_poll_delay = first_poll_delay
        self.poll_interval = poll_interval
        self.cancel = cancel
        self._on_activity: ActivitySink = on_activity or _ignore

    # -- HTTP ---------------------------------------------------------------

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Call-E-Integration": "ringedingeding/0.1.0",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            url, data=data, headers=self._headers(idempotency_key), method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=self.request_timeout) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            # Masked: upstream errors sometimes echo the number back.
            raise RuntimeError(f"HTTP {error.code} from {path}: {mask_text(detail)}") from None
        except urllib.error.URLError as error:
            raise RuntimeError(f"cannot reach {self.base_url}: {error.reason}") from None
        parsed = json.loads(payload) if payload.strip() else {}
        if not isinstance(parsed, dict):
            raise RuntimeError(f"unexpected response shape from {path}")
        return parsed

    # -- lifecycle ----------------------------------------------------------

    def place_one(self, request: CallRequest) -> CallOutcome:
        body = request.payload(redact_phone=False)
        created = self._request(
            "POST", "/v1/calls", body=body, idempotency_key=request.idempotency_key
        )
        call_id = _call_id(created)
        if not call_id:
            raise RuntimeError("POST /v1/calls returned no call id")
        final = self._poll_until_terminal(call_id)
        recipients = final.get("recipients")
        recipient = recipients[0] if isinstance(recipients, list) and recipients else {}
        return _outcome_from(
            participant_id=request.participant.id,
            call=final,
            recipient=recipient if isinstance(recipient, dict) else {},
            run_id=call_id,
        )

    def _poll_until_terminal(self, call_id: str) -> dict[str, Any]:
        """Poll until ``status`` reaches a terminal value, reporting progress.

        Two different fields do two different jobs here, and swapping them is
        the mistake this whole method exists to avoid:

        ``activity``
            what is happening right now. Read on every poll and forwarded to
            the caller line by line.
        ``status``
            when it is over. Useless as progress — it stayed on ``PREPARING``
            through an entire conversation — but it is what finally says
            ``COMPLETED``, and only then does ``result.transcript`` appear.
        """
        deadline = time.monotonic() + self.poll_timeout
        reported = 0
        last_seen: Any = None
        self._sleep(self.first_poll_delay, deadline)
        while True:
            payload = self._request("GET", f"/v1/calls/{call_id}")
            last_seen = payload.get("status")
            # known(), not parse(): an unrecognised status must not end the
            # wait. The terminal statuses are a closed documented list, so
            # anything outside it — PREPARING, or something never seen before —
            # means the call is still running. Treating it as FAILED would
            # declare a conversation dead while it is still going on, and the
            # next run would then dial that person a second time.
            status = CallStatus.known(last_seen)
            terminal = status is not None and status.is_terminal
            reported = self._report_activity(payload, reported, final=terminal)
            if terminal:
                return payload
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"call {call_id} never reached a terminal status within "
                    f"{self.poll_timeout:.0f}s; last status was {last_seen!r}"
                )
            self._sleep(self.poll_interval, deadline)

    def _report_activity(self, payload: dict[str, Any], reported: int, *, final: bool) -> int:
        """Forward activity lines that have not been shown yet.

        While the call runs, the newest line is deliberately **held back** for
        one poll. Speech recognition streams a rough version and corrects it a
        fraction of a second later ("hallo" then "Hallo."), so showing the last
        line immediately means showing the version that is about to be wrong.
        On the final poll everything remaining is flushed.
        """
        lines = dedupe(extract_activity(payload))
        limit = len(lines) if final else max(0, len(lines) - 1)
        for line in lines[reported:limit]:
            self._on_activity(line)
        return max(reported, limit)

    def _sleep(self, seconds: float, deadline: float) -> None:
        """Sleep in short steps so Ctrl-C is noticed promptly."""
        end = min(time.monotonic() + seconds, deadline + self.poll_interval)
        while time.monotonic() < end:
            if self.cancel is not None and self.cancel.is_set():
                return
            time.sleep(min(0.5, max(0.0, end - time.monotonic())))


class CalleBatchTransport(CalleTransport):
    """One ``POST /v1/calls`` carrying every recipient of the poll.

    This is the shape the API documents for multi-recipient tasks and the reason
    this project fits CALL-E rather than fighting it. Untested against a real
    account — see the module docstring.
    """

    name = "calle-batch"
    supports_batch = True

    def place_many(
        self,
        requests: Sequence[CallRequest],
        *,
        concurrency: int = 1,
        cancel: threading.Event | None = None,
    ) -> Iterator[CallOutcome]:
        if not requests:
            return
        if cancel is not None and cancel.is_set():
            return

        first = requests[0]
        body = first.payload(redact_phone=False)
        body["recipients"] = [
            {
                "phones": [request.participant.phone_e164],
                "region": request.poll.region,
                "locale": request.poll.locale,
            }
            for request in requests
        ]
        # One batch, one intent, one idempotency key.
        batch_key = f"{first.idempotency_key}_batch{len(requests)}"

        try:
            created = self._request("POST", "/v1/calls", body=body, idempotency_key=batch_key)
            call_id = _call_id(created)
            if not call_id:
                raise RuntimeError("POST /v1/calls returned no call id")
            final = self._poll_until_terminal(call_id)
        except Exception as error:  # noqa: BLE001 - report per participant
            message = f"{type(error).__name__}: {error}"
            for request in requests:
                yield CallOutcome(
                    participant_id=request.participant.id,
                    status=CallStatus.FAILED,
                    error=message,
                )
            return

        recipients = final.get("recipients")
        if not isinstance(recipients, list) or len(recipients) != len(requests):
            # Refuse to guess. A misattributed answer is worse than no answer.
            got = len(recipients) if isinstance(recipients, list) else "none"
            for request in requests:
                yield CallOutcome(
                    participant_id=request.participant.id,
                    status=CallStatus.FAILED,
                    error=(
                        f"batch response has {got} recipient entries for "
                        f"{len(requests)} recipients; refusing to map answers by "
                        "position. Re-run with --serial."
                    ),
                    run_id=call_id,
                )
            return

        for request, recipient in zip(requests, recipients):
            yield _outcome_from(
                participant_id=request.participant.id,
                call=final,
                recipient=recipient if isinstance(recipient, dict) else {},
                run_id=call_id,
            )


def _call_id(payload: dict[str, Any]) -> str | None:
    for key in ("id", "call_id", "callId"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _outcome_from(
    *,
    participant_id: str,
    call: dict[str, Any],
    recipient: dict[str, Any],
    run_id: str | None,
) -> CallOutcome:
    """Map an API payload onto a :class:`CallOutcome`.

    Per-recipient status wins over the batch status: in a batch of six, one
    ``NO_ANSWER`` must not turn the other five into failures, and a batch that
    "completed" says nothing about whether a given person picked up.

    The transcript is looked for **per recipient first**. In a batch there is
    one conversation per person, so the call-level transcript is only used when
    a single recipient is involved and no per-recipient text exists — handing
    somebody else's conversation to the wrong person would be exactly the kind
    of mix-up the length check above refuses to make.
    """
    status_source = recipient.get("status", call.get("status"))
    status = CallStatus.parse(status_source)
    structured = recipient.get("structured_result") or recipient.get("structuredResult") or {}
    if not isinstance(structured, dict):
        structured = {}
    summary = ""
    for key in ("summary", "post_summary", "message"):
        value = recipient.get(key) or call.get(key)
        if isinstance(value, str) and value.strip():
            summary = mask_text(value.strip())
            break

    transcript = extract_transcript(recipient)
    if not transcript:
        others = call.get("recipients")
        single = not isinstance(others, list) or len(others) <= 1
        if single:
            transcript = extract_transcript(call)

    return CallOutcome(
        participant_id=participant_id,
        status=status,
        structured=structured,
        summary=summary,
        transcript=mask_text(transcript),
        run_id=run_id,
    )
