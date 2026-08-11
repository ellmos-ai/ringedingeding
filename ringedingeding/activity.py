"""Reading a call while it happens, and reading the transcript afterwards.

Both of these were wrong in the first version of this project, and both were
corrected by measuring the real service (FINDINGS.md, sections 1-3).

**Progress does not come from ``status``.** The status field stayed on
``PREPARING`` while the two sides were already talking, and only flipped to
``COMPLETED`` roughly 24 seconds after the conversation had ended. Anything
that waits for ``status`` to move watches a stone.

**Progress comes from ``activity``**, a growing list of lines with millisecond
timestamps that carries both sides of the conversation::

    00:00:00.000 | Call is ringing.
    00:00:04.000 | Call connected.
    00:00:05.000 | Bot is speaking: This is an automated call on behalf of the organizer.
    00:00:06.000 | Callee said: hallo
    00:00:07.000 | Callee said: Hallo.

The last two lines are the same sentence twice. Speech recognition streams a
rough version first and corrects it a fraction of a second later, so anything
displaying these lines has to fold them together — see :func:`dedupe`.

**The transcript is not where the field name suggests.** ``transcript`` at the
top level stayed ``null`` even after the call finished; the text lives in
``result.transcript``, as one string in ``[mm:ss] SPEAKER: Text`` form.

The exact JSON shape of an ``activity`` entry was only ever seen rendered, so
the parser below accepts strings, dictionaries and a few plausible key names
rather than insisting on one. Whatever it cannot interpret it keeps verbatim
instead of dropping.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Sequence

from .phone import mask_text

__all__ = [
    "Speaker",
    "ActivityLine",
    "TranscriptLine",
    "parse_activity",
    "dedupe",
    "extract_activity",
    "extract_transcript",
    "parse_transcript",
    "CORRECTION_WINDOW_SECONDS",
]

CORRECTION_WINDOW_SECONDS = 5.0
"""How close two lines must be before the later one is treated as a correction
of the earlier one. The observed gap was 0.67 s; five seconds leaves room
without swallowing somebody genuinely repeating themselves a minute later."""


class Speaker(str, Enum):
    BOT = "bot"
    CALLEE = "callee"
    SYSTEM = "system"
    """Call lifecycle notes: ringing, connected, ended."""


_PREFIXES: tuple[tuple[re.Pattern[str], Speaker], ...] = (
    (re.compile(r"^bot\s+is\s+speaking\s*:\s*", re.IGNORECASE), Speaker.BOT),
    (re.compile(r"^(?:agent|assistant)\s+(?:is\s+)?(?:speaking|said)\s*:\s*", re.IGNORECASE), Speaker.BOT),
    (re.compile(r"^callee\s+said\s*:\s*", re.IGNORECASE), Speaker.CALLEE),
    (re.compile(r"^(?:user|customer|human)\s+said\s*:\s*", re.IGNORECASE), Speaker.CALLEE),
)

# "00:00:00.000 | Call is ringing." — the rendering seen in the evidence log.
_RENDERED = re.compile(r"^\s*(?P<stamp>[0-9T:.\-+Z]{5,32})\s*\|\s*(?P<text>.*)$")

# "[00:12] BOT: ..." — the transcript form.
_TRANSCRIPT_LINE = re.compile(
    r"^\s*\[(?P<stamp>\d{1,3}:\d{2}(?::\d{2})?)\]\s*(?P<speaker>[A-Za-z_ ]{1,20}?)\s*:\s*(?P<text>.*)$"
)

_PUNCTUATION = re.compile(r"[.,;:!?…\"'„“”‚‘’()\[\]-]+")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class ActivityLine:
    """One entry of the ``activity`` list."""

    text: str
    """What was said or what happened, without the ``Bot is speaking:`` prefix."""

    speaker: Speaker = Speaker.SYSTEM
    timestamp: str = ""
    """Verbatim as delivered. Not parsed into a datetime — the format is not
    guaranteed and a wrong parse would be worse than a string."""

    raw: str = ""
    """The untouched entry, so nothing is lost by the interpretation above."""

    @property
    def is_speech(self) -> bool:
        return self.speaker in (Speaker.BOT, Speaker.CALLEE)

    @property
    def words(self) -> tuple[str, ...]:
        """Lower-case words without punctuation — for correction detection only.

        Punctuation is dropped rather than just trimmed at the end, because a
        correction typically adds it in the middle: "yes go" becomes "Yes, go
        ahead." Comparing whole words (not characters) then keeps "yes go" from
        looking like the start of "yes gorilla".
        """
        cleaned = _PUNCTUATION.sub(" ", self.text)
        return tuple(_WHITESPACE.sub(" ", cleaned).strip().casefold().split())

    def display(self) -> str:
        """One line for the console. Masked: this text is not ours."""
        who = {Speaker.BOT: "bot   ", Speaker.CALLEE: "callee", Speaker.SYSTEM: "--    "}[
            self.speaker
        ]
        stamp = f"{self.timestamp} " if self.timestamp else ""
        return f"{stamp}{who} | {mask_text(self.text)}"


@dataclass(frozen=True)
class TranscriptLine:
    """One line of ``result.transcript``."""

    offset: str
    """``mm:ss`` from the start of the call, as delivered."""

    speaker: str
    """``BOT`` or ``USER`` in the observed call. Kept verbatim, not mapped, so
    an unseen speaker label does not disappear."""

    text: str


def _seconds_from_stamp(stamp: str) -> float | None:
    """Best-effort clock reading, only used to judge nearness in time."""
    match = re.search(r"(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?", stamp)
    if not match:
        return None
    hours, minutes, seconds, fraction = match.groups()
    total = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    if fraction:
        total += int(fraction) / (10 ** len(fraction))
    return float(total)


def _split_speaker(text: str) -> tuple[Speaker, str]:
    for pattern, speaker in _PREFIXES:
        if pattern.match(text):
            return speaker, pattern.sub("", text, count=1).strip()
    return Speaker.SYSTEM, text.strip()


def _line_from_string(entry: str) -> ActivityLine:
    raw = entry.rstrip()
    body = raw
    timestamp = ""
    rendered = _RENDERED.match(raw)
    if rendered:
        timestamp = rendered.group("stamp").strip()
        body = rendered.group("text").strip()
    speaker, text = _split_speaker(body)
    return ActivityLine(text=text, speaker=speaker, timestamp=timestamp, raw=raw)


def _first_string(mapping: dict[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _line_from_mapping(entry: dict[str, Any]) -> ActivityLine:
    text = _first_string(
        entry, ("message", "text", "description", "detail", "content", "event", "activity")
    )
    timestamp = _first_string(entry, ("timestamp", "time", "at", "created_at", "createdAt"))
    raw = f"{timestamp} | {text}".strip(" |") if (timestamp or text) else str(entry)

    speaker, body = _split_speaker(text)
    # An explicit role field wins over the sentence prefix, when there is one.
    role = _first_string(entry, ("speaker", "role", "actor", "source")).lower()
    if role in ("bot", "agent", "assistant", "ai"):
        speaker = Speaker.BOT
    elif role in ("callee", "user", "customer", "human", "person"):
        speaker = Speaker.CALLEE
    return ActivityLine(text=body, speaker=speaker, timestamp=timestamp, raw=raw)


def parse_activity(entries: Any) -> list[ActivityLine]:
    """Turn whatever ``activity`` contained into lines.

    Accepts a list of strings, a list of dictionaries, a single string with
    newlines, or nothing at all. Unknown shapes become a system line holding
    their ``repr`` rather than being dropped silently.
    """
    if entries is None:
        return []
    if isinstance(entries, str):
        return [_line_from_string(part) for part in entries.splitlines() if part.strip()]
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, Iterable):
        return []

    lines: list[ActivityLine] = []
    for entry in entries:
        if isinstance(entry, str):
            if entry.strip():
                lines.append(_line_from_string(entry))
        elif isinstance(entry, dict):
            lines.append(_line_from_mapping(entry))
        else:
            lines.append(ActivityLine(text=str(entry), raw=str(entry)))
    return lines


def dedupe(
    lines: Sequence[ActivityLine],
    *,
    window_seconds: float = CORRECTION_WINDOW_SECONDS,
) -> list[ActivityLine]:
    """Fold streamed speech-recognition corrections into their final version.

    ``Callee said: hallo`` followed 0.67 s later by ``Callee said: Hallo.`` is
    one utterance, not two. The later line replaces the earlier one when all of
    the following hold:

    * same speaker, and that speaker is a person or the bot (never lifecycle
      notes — two separate "Call is ringing" lines are two real events),
    * the earlier line's words open the later line's words, ignoring case and
      punctuation,
    * they are close together in time, when timestamps allow that judgement.

    This is a heuristic on undocumented behaviour. It only ever drops a line
    whose words all reappear, in order, at the start of the line that replaces
    it — so nothing a person said can be lost. The transcript fetched at the
    end of the call is untouched by any of this and remains the record.
    """
    result: list[ActivityLine] = []
    for line in lines:
        if result and line.is_speech:
            previous = result[-1]
            if previous.speaker is line.speaker and _is_correction(
                previous, line, window_seconds=window_seconds
            ):
                result[-1] = line
                continue
        result.append(line)
    return result


def _is_correction(
    earlier: ActivityLine, later: ActivityLine, *, window_seconds: float
) -> bool:
    old, new = earlier.words, later.words
    if not old or not new:
        return False
    if len(old) > len(new) or new[: len(old)] != old:
        return False
    start = _seconds_from_stamp(earlier.timestamp)
    end = _seconds_from_stamp(later.timestamp)
    if start is not None and end is not None:
        gap = end - start
        if gap < 0 or gap > window_seconds:
            return False
    return True


# --------------------------------------------------------------------------
# digging the fields out of a response
# --------------------------------------------------------------------------

_ACTIVITY_PATHS: tuple[tuple[str, ...], ...] = (
    ("activity",),
    ("result", "activity"),
    ("structuredContent", "activity"),
    ("structuredContent", "result", "activity"),
)

_TRANSCRIPT_PATHS: tuple[tuple[str, ...], ...] = (
    # Measured: this is where it actually is.
    ("result", "transcript"),
    ("structuredContent", "result", "transcript"),
    # Measured to be null, kept as a last resort in case that ever changes.
    ("structuredContent", "transcript"),
    ("transcript",),
)

# Measured 2026-08-11 (FINDINGS.md section 9): a recipient carries neither of
# the paths above at all. What it has instead is ``attempts``, a list of dial
# tries, each with its own ``transcript_turns`` — a list of ``{offset_seconds,
# speaker, text}`` dictionaries rather than one pre-formatted string. Only one
# entry was ever observed in ``attempts``, even for a call the service redialled
# internally, but the shape is a list, so it is walked rather than indexed.
_TURN_SPEAKER_MAP: dict[str, str] = {
    "bot": "BOT",
    "agent": "BOT",
    "assistant": "BOT",
    "ai": "BOT",
    "user": "USER",
    "callee": "USER",
    "customer": "USER",
    "human": "USER",
}


def _dig(payload: Any, path: Sequence[str]) -> Any:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def extract_activity(payload: Any) -> list[ActivityLine]:
    """Find and parse the activity list wherever the response keeps it."""
    for path in _ACTIVITY_PATHS:
        found = _dig(payload, path)
        if found:
            return parse_activity(found)
    return []


def _format_offset_seconds(seconds: Any) -> str:
    """``offset_seconds`` (an int or float) rendered as ``mm:ss``.

    Matches the ``[mm:ss] SPEAKER: Text`` convention of section 3 exactly, so a
    transcript built from turns parses the same way as one that arrived as a
    ready-made string.
    """
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        total = 0
    total = max(0, total)
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


def _transcript_from_turns(turns: Any) -> str:
    """Render a ``transcript_turns`` list into the established string form."""
    if not isinstance(turns, list):
        return ""
    lines: list[str] = []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        text = _first_string(turn, ("text", "message", "content"))
        if not text:
            continue
        speaker_raw = _first_string(turn, ("speaker", "role", "actor")).strip().lower()
        speaker = _TURN_SPEAKER_MAP.get(speaker_raw, speaker_raw.upper() or "SYSTEM")
        stamp = _format_offset_seconds(turn.get("offset_seconds"))
        lines.append(f"[{stamp}] {speaker}: {text}")
    return "\n".join(lines)


def _transcript_from_attempts(payload: Any) -> str:
    """Measured 2026-08-11 (FINDINGS.md section 9): the only place a
    recipient's transcript lives when ``result.transcript`` never existed.

    Walked from the end: not observed with more than one attempt, but a retry
    that finally connects must not hand back an earlier, empty try.
    """
    if not isinstance(payload, dict):
        return ""
    attempts = payload.get("attempts")
    if isinstance(attempts, list):
        for attempt in reversed(attempts):
            if not isinstance(attempt, dict):
                continue
            transcript = _transcript_from_turns(attempt.get("transcript_turns"))
            if transcript:
                return transcript
        return ""
    # Permissive fallback: turns directly on the payload, without the
    # ``attempts`` wrapper. Not observed, but plausible — this module accepts
    # several shapes rather than insisting on the one that was seen once.
    return _transcript_from_turns(payload.get("transcript_turns"))


def extract_transcript(payload: Any) -> str:
    """Return the transcript string, or ``""`` when there is none.

    Looks in ``result.transcript`` first because that is where the real service
    put it. ``transcript`` at the top level was measured to be ``null`` even
    after the call had finished, so it is checked last. ``attempts[].transcript_turns``
    (section 9) is the final fallback, for the shape that carries no top-level
    string transcript at all.
    """
    for path in _TRANSCRIPT_PATHS:
        found = _dig(payload, path)
        if isinstance(found, str) and found.strip():
            return found.strip()
        if isinstance(found, list) and found:
            # Not observed, but a list of lines would be the obvious other shape.
            parts = [str(item).strip() for item in found if str(item).strip()]
            if parts:
                return "\n".join(parts)
    return _transcript_from_attempts(payload)


def parse_transcript(text: str) -> list[TranscriptLine]:
    """Split ``[mm:ss] SPEAKER: Text`` into lines.

    A line that does not match is attached to the previous one, because a
    transcript containing a newline inside an utterance is far more likely than
    a transcript that suddenly changes format.
    """
    lines: list[TranscriptLine] = []
    for raw in (text or "").splitlines():
        if not raw.strip():
            continue
        match = _TRANSCRIPT_LINE.match(raw)
        if match:
            lines.append(
                TranscriptLine(
                    offset=match.group("stamp"),
                    speaker=match.group("speaker").strip().upper(),
                    text=match.group("text").strip(),
                )
            )
        elif lines:
            previous = lines[-1]
            lines[-1] = TranscriptLine(
                offset=previous.offset,
                speaker=previous.speaker,
                text=f"{previous.text} {raw.strip()}".strip(),
            )
        else:
            lines.append(TranscriptLine(offset="", speaker="", text=raw.strip()))
    return lines
