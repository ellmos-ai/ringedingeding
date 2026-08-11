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
* roughly 40 seconds pass before a telephone rings, whatever the call,
* a mailbox pickup is reported as a plain ``COMPLETED`` call, with no
  ``VOICEMAIL`` status on the wire — read from the transcript instead
  (FINDINGS.md section 9, 2026-08-11, relayed by the operator),
* an active decline arrives as a generic ``FAILED``, with the real terminal
  status folded into ``failure_message`` (FINDINGS.md section 9, same date),
* a recipient without ``result.transcript`` carries the conversation in
  ``attempts[].transcript_turns`` instead — a list of turn dictionaries, not
  a ready-made string (FINDINGS.md section 9, same date).

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
* the exact wording CALL-E uses for BUSY, NO_ANSWER, CANCELED or EXPIRED
  pickups — only the mailbox and decline cases above have been observed.

No code in this module has been executed against the live API — the API itself
was, by the operator, and the payloads it returned are what section 9 records.
See EVIDENCE.md for what ran in this repository.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Iterator, Sequence

from ..activity import ActivityLine, dedupe, extract_activity, extract_transcript, parse_transcript
from ..calle_credentials import (
    API_KEY_ENV,
    BASE_URL_ENV,
    DEFAULT_BASE_URL,
    CalleCredentialError,
    load_calle_settings,
)
from ..models import CallStatus
from ..phone import mask_text
from ..safety import LiveCallBlocked
from ..timings import LEAD_SECONDS
from .base import CallOutcome, CallRequest, CallTransport

__all__ = ["CalleTransport", "CalleBatchTransport", "DEFAULT_BASE_URL", "API_KEY_ENV"]

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
        credential_override: str | None = None,
        base_url: str | None = None,
        env_file: str | None = None,
        config_file: str | None = None,
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
        if credential_override:
            # Server mode huckepack-only-host: this key belongs to the visitor
            # and outranks everything the host has configured. Consulting the
            # resolver here would charge the host for someone else's call —
            # quietly, which is the worst way for it to happen.
            settings = None
            self._api_key = credential_override
        else:
            try:
                settings = load_calle_settings(env_file=env_file, config_file=config_file)
            except CalleCredentialError as error:
                if not api_key:
                    raise LiveCallBlocked(str(error)) from None
                settings = None
            # ``api_key`` remains an internal dependency-injection hook for callers
            # that already use it. User configuration always goes through the
            # documented resolver, and therefore keeps its strict priority order.
            self._api_key = settings.api_key if settings is not None else api_key or ""
        self.base_url = (
            base_url or (settings.base_url if settings is not None else DEFAULT_BASE_URL)
        ).rstrip("/")
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


# --------------------------------------------------------------------------
# a mailbox pickup, mapped onto its own status
# --------------------------------------------------------------------------
#
# Measured 2026-08-11 (FINDINGS.md section 9, relayed by the operator from a
# live call): CALL-E reports a mailbox pickup as a plain "completed" call,
# task_completed true, indistinguishable from a real conversation by status
# alone. There is no VOICEMAIL status on the wire to read — it has to be read
# out of the transcript instead.
#
# Two tiers, because not every telltale phrase is equally trustworthy. A
# phrase that only ever occurs on an answering machine (the beep tone, the
# German words for mailbox and answering machine) is decisive by itself,
# anywhere a callee or bot line says it. A phrase a real participant could
# plausibly say about their *own* availability in one of this tool's polls —
# "I won't be reachable", "leave a message [with someone else]" — is not
# trusted alone. It only counts when it opens the conversation (the way an
# answering machine's greeting always does) *and* the agent's own evidence
# text independently names the same thing.

_STRONG_VOICEMAIL_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"nachricht\s+nach\s+dem\s+signalton",
        r"\bsignalton\b",
        r"anrufbeantworter",
        r"\bsprachbox\b",
        r"\bmailbox\b",
        r"\bvoicemail\b",
        r"answering\s+machine",
        r"after\s+the\s+(?:tone|beep)",
    )
)

_WEAK_VOICEMAIL_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"nicht\s+erreichbar",
        r"hinterlassen\s+sie\s+eine\s+nachricht",
        r"leave\s+a\s+message",
    )
)


def _matches_any(text: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _looks_like_voicemail(transcript: str, evidence_text: str) -> bool:
    """Conservative on purpose: only ``callee``/``user`` lines are read.

    The bot side is never trusted for this. FINDINGS.md section 4 measured
    that the planner adds voicemail-handling instructions to the bot's own
    behaviour on its own initiative, never asked for — so a bot line
    mentioning "mailbox" is evidence of an instruction, not of a mailbox.
    """
    lines = [line for line in parse_transcript(transcript) if line.speaker in ("USER", "CALLEE")]
    if not lines:
        return False
    callee_text = " ".join(line.text for line in lines)
    if _matches_any(callee_text, _STRONG_VOICEMAIL_PATTERNS):
        return True
    if not _matches_any(lines[0].text, _WEAK_VOICEMAIL_PATTERNS):
        return False
    return _matches_any(evidence_text, (*_STRONG_VOICEMAIL_PATTERNS, *_WEAK_VOICEMAIL_PATTERNS))


# --------------------------------------------------------------------------
# a generic FAILED, recovered from the failure message
# --------------------------------------------------------------------------
#
# Measured 2026-08-11 (FINDINGS.md section 9, relayed by the operator): an
# active decline arrives as the generic top-level status "failed", with the
# real terminal status folded into ``failure_message``:
# "calling task status=DECLINED (Hangup by: user)". Nothing in this project
# read ``failure_message`` before this — an active refusal was landing in
# ``Bucket.UNREACHED`` next to a phone nobody answered, which is exactly the
# distinction ``CallStatus`` exists to keep apart.

_FAILURE_STATUS_PATTERN = re.compile(r"status\s*=\s*([A-Za-z_]+)")


def _status_from_failure_message(message: str) -> CallStatus | None:
    """The status ``failure_message`` claims, if this program knows it.

    Only a recognised token is trusted — an unfamiliar one is left as
    ``FAILED`` rather than guessed at, the same rule :meth:`CallStatus.known`
    already applies while polling.
    """
    match = _FAILURE_STATUS_PATTERN.search(message)
    if not match:
        return None
    return CallStatus.known(match.group(1))


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

    Two refinements sit between the raw status and the outcome, both measured
    2026-08-11 (see the sections above): a generic ``FAILED`` is checked
    against ``failure_message`` for the real status it may be hiding, and a
    ``COMPLETED`` call is checked against its transcript for a mailbox pickup.
    """
    status_source = recipient.get("status", call.get("status"))
    status = CallStatus.parse(status_source)
    error: str | None = None

    if status is CallStatus.FAILED:
        failure_message = str(
            recipient.get("failure_message") or call.get("failure_message") or ""
        ).strip()
        embedded = _status_from_failure_message(failure_message)
        if embedded is not None:
            status = embedded
        elif failure_message:
            error = mask_text(failure_message)

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

    if status is CallStatus.COMPLETED:
        evidence = recipient.get("evidence") or call.get("evidence")
        evidence_text = (
            " ".join(str(item) for item in evidence) if isinstance(evidence, list) else ""
        )
        if _looks_like_voicemail(transcript, evidence_text):
            status = CallStatus.VOICEMAIL

    return CallOutcome(
        participant_id=participant_id,
        status=status,
        structured=structured,
        summary=summary,
        transcript=mask_text(transcript),
        run_id=run_id,
        error=error,
    )
