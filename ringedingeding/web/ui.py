"""Turning domain objects into things a template can print.

Everything here is presentation and nothing here decides anything. The four
states of a slot are computed in :mod:`ringedingeding.service`; this module only
gives them a colour and a symbol.

Two small pieces of behaviour do live here, because they are about display and
nowhere else:

* a person without a photograph still gets a face — initials on a colour derived
  from their name, so the calendar reads at a glance ("weil wir Menschen nicht
  so heißen"),
* the calendar groups slots by day, which is how a person reads a week and not
  how the database stores one.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

from ..models import CallStatus
from ..projects import WEEKDAYS
from ..service import Board, Person, SlotView
from ..translator import TranslationSystem

__all__ = [
    "MONTHS",
    "CalendarDay",
    "LiveRow",
    "avatar_colour",
    "calendar_days",
    "live_rows",
    "status_word",
]

MONTHS = {
    "de": (
        "Januar", "Februar", "März", "April", "Mai", "Juni",
        "Juli", "August", "September", "Oktober", "November", "Dezember",
    ),
    "en": (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ),
}

# Muted, readable on white, distinguishable from the green/red state colours so
# a face never looks like a verdict.
_AVATAR_COLOURS = (
    "#5b7c99", "#7c6a9c", "#4f8a76", "#9c7b5b", "#8a5b6a",
    "#5b8a9c", "#6a7c4f", "#9c8a5b", "#7a5b9c", "#4f6a8a",
)


def avatar_colour(key: str) -> str:
    """A stable colour for a name. Same person, same colour, every time."""
    digest = hashlib.sha256(str(key or "?").encode("utf-8")).digest()
    return _AVATAR_COLOURS[digest[0] % len(_AVATAR_COLOURS)]


# --------------------------------------------------------------------------
# calendar
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CalendarDay:
    """One day of the project calendar with its slots."""

    key: str
    """``YYYY-MM-DD``, or ``""`` for slots that have no date (recurring)."""

    weekday: str
    day_label: str
    slots: tuple[SlotView, ...]

    @property
    def best_count(self) -> int:
        return max((view.count for view in self.slots), default=0)


def calendar_days(board: Board, language: str = "de") -> list[CalendarDay]:
    """Group the slots of a board by day, in the project's own order."""
    german = str(language).lower().startswith("de")
    names = WEEKDAYS["de"] if german else WEEKDAYS["en"]
    months = MONTHS["de"] if german else MONTHS["en"]

    grouped: dict[str, list[SlotView]] = {}
    order: list[str] = []
    for view in board.slots:
        key = view.slot.day_date or ""
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(view)

    days: list[CalendarDay] = []
    for key in order:
        try:
            day = date.fromisoformat(key) if key else None
        except ValueError:
            day = None
        if day is not None:
            weekday = names[day.weekday()]
            label = f"{day.day}. {months[day.month - 1]}"
        else:
            # A slot without a date is still a slot: a recurring weekday, or a
            # label a fixture brought with it. It gets a row rather than being
            # dropped for not fitting the grid.
            weekday = ""
            label = grouped[key][0].slot.label if grouped[key] else "—"
        days.append(
            CalendarDay(
                key=key, weekday=weekday, day_label=label, slots=tuple(grouped[key])
            )
        )
    return days


# --------------------------------------------------------------------------
# live view
# --------------------------------------------------------------------------

_STATUS_WORDS = {
    CallStatus.PENDING: "wartet",
    CallStatus.SKIPPED: "übersprungen",
    CallStatus.PREPARING: "im Gespräch",
    CallStatus.COMPLETED: "hat geantwortet",
    CallStatus.FAILED: "fehlgeschlagen",
    CallStatus.NO_ANSWER: "niemand da",
    CallStatus.DECLINED: "weggedrückt",
    CallStatus.CANCELED: "abgebrochen",
    CallStatus.VOICEMAIL: "Anrufbeantworter",
    CallStatus.BUSY: "besetzt",
    CallStatus.EXPIRED: "abgelaufen",
}

# The end states of ABLAUF.md section 2, and the three groups it puts them in.
# The grouping carries a judgement and is worth spelling out:
#
# ``declined``
#     Somebody was there and said no — to the call or to answering. A definite
#     negative, shown in red like "kann nicht".
# ``absent``
#     Nobody was there. **Uncertain, not negative**, so a question mark and grey
#     — never red, and never struck through, because striking a name through
#     reads as "this person is out" when in truth nothing is known about them.
# ``failed``
#     Something went wrong on the way. Red, and it has to say why.
_DECLINED_STATUSES = (CallStatus.DECLINED,)
_ABSENT_STATUSES = (CallStatus.NO_ANSWER, CallStatus.BUSY, CallStatus.VOICEMAIL)
_FAILED_STATUSES = (
    CallStatus.FAILED,
    CallStatus.EXPIRED,
    CallStatus.CANCELED,
    CallStatus.SKIPPED,
)


def status_word(status: CallStatus | str, language: str = "de") -> str:
    """The localized word for a call status, keeping every status distinct.

    ``NO_ANSWER``, ``BUSY`` and ``VOICEMAIL`` deliberately get three different
    words. Collapsing them into "nicht erreicht" would throw away the one thing
    that tells somebody whether calling again is worth it.
    """
    known = CallStatus.known(status)
    german = _STATUS_WORDS.get(known, str(status)) if known else str(status)
    return TranslationSystem(language=language).t(german)


@dataclass(frozen=True)
class LiveRow:
    """One person in the live view."""

    ref: str
    name: str
    contact_id: str | None
    initials: str
    has_photo: bool
    state: str
    """``waiting`` | ``calling`` | ``answered`` | ``declined`` | ``absent``
    | ``failed`` — the end states of ABLAUF.md section 2."""

    detail: str = ""

    @property
    def colour(self) -> str:
        return avatar_colour(self.contact_id or self.name)

    @property
    def uncertain(self) -> bool:
        """Whether nothing is known about this person yet.

        Drives the question mark. Kept as a property rather than being decided
        in the template so the live view and any later report cannot disagree
        about who counts as unknown.
        """
        return self.state in ("waiting", "absent")


def live_rows(
    participants: Sequence,
    answers: dict,
    contacts: dict,
    current_ref: str | None,
    language: str = "de",
) -> list[LiveRow]:
    """Build the live list from stored state plus who is on the phone now.

    Stored state first, live event second: that ordering is what makes the page
    correct after a reload. The only thing that comes from the running job is
    which telephone symbol is moving.

    The six end states come from ABLAUF.md section 2 and are deliberately not
    collapsed into "reached / not reached": somebody who pressed the call away
    told you something, somebody whose telephone rang out did not.
    """
    rows: list[LiveRow] = []
    translator = TranslationSystem(language=language)
    for participant in participants:
        answer = answers.get(participant.id)
        contact = contacts.get(participant.contact_id) if participant.contact_id else None
        if answer is None:
            state = "calling" if participant.ref == current_ref else "waiting"
            detail = translator.t("wird angerufen") if state == "calling" else translator.t("wartet")
        else:
            status = answer.call_status
            if status is CallStatus.COMPLETED and answer.structured.get("refused") is True:
                state, detail = "declined", translator.t("wollte nicht antworten")
            elif status is CallStatus.COMPLETED:
                state, detail = "answered", status_word(status, language)
            elif status in _DECLINED_STATUSES:
                state, detail = "declined", status_word(status, language)
            elif status in _ABSENT_STATUSES:
                state, detail = "absent", status_word(status, language)
            elif status in (CallStatus.PENDING, CallStatus.PREPARING):
                state, detail = "calling", status_word(status, language)
            else:
                # FAILED, EXPIRED, CANCELED, SKIPPED — red, and it has to say why.
                state = "failed"
                detail = status_word(status, language)
                if answer.error:
                    detail = f"{detail}: {answer.error}"
        rows.append(
            LiveRow(
                ref=participant.ref,
                name=participant.name,
                contact_id=participant.contact_id,
                initials=contact.initials if contact else participant.name[:2].upper(),
                has_photo=bool(contact and contact.has_photo),
                state=state,
                detail=detail,
            )
        )
    return rows


def person_colour(person: Person) -> str:
    return avatar_colour(person.contact_id or person.name)


def any_photo(people: Iterable[Person]) -> bool:
    return any(person.has_photo for person in people)
