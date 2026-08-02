"""The project layer: contact book, date candidates, criteria, decision.

A *poll* (:mod:`ringedingeding.store`) is one question put to several people.
A *project* sits above it and is what a person actually works on: an occasion,
a set of candidate dates, the people to invite, the wording, and — at the end —
one decision. One project owns several polls, because asking who can make it and
telling everybody afterwards are two different conversations.

Three modelling choices here exist for the sake of the later stages, and are
worth naming because each of them is cheap now and expensive later:

**Phone numbers live in ``contact_channel``, not on the contact.**
    The second channel (e-mail) is then a row, not a migration. It also makes
    "cannot be called at all" a property of the contact rather than a null check
    scattered through the code.

**One row shape covers all six kinds of date.**
    ``day_date``/``end_date``/``weekday``/``start_time``/``end_time``/``all_day``
    together express a single timed slot, a whole day, a week, a month, a
    multi-day span and a recurring weekday. Stage 1 fills two of those shapes;
    the rest need a different slot *generator*, not a different table.

**Groups exist from the first day, empty.**
    A group profile ("meine Ritterrunde") carries its own phrases and its own
    freely named questions in stage 2. Both point at ``contact_group.id``, so
    the tables are created now and stay unused until then.

Nothing derived is stored. Whether somebody can make a slot is computed from the
answers every time it is needed — a second copy of that would drift.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, time
from typing import Any, Sequence

from .models import new_id
from .phone import mask, normalize_e164
from .store import Store, utc_now

__all__ = [
    "ProjectMode",
    "DateKind",
    "ChannelKind",
    "ProjectState",
    "Channel",
    "Contact",
    "ContactGroup",
    "Project",
    "ProjectQuestion",
    "Slot",
    "Invitee",
    "Phrase",
    "Criteria",
    "Decision",
    "ProjectStore",
    "slot_label",
    "WEEKDAYS",
]


# --------------------------------------------------------------------------
# vocabulary
# --------------------------------------------------------------------------


class ProjectMode:
    """What the project is for."""

    SCHEDULE = "schedule"
    """Terminkonzil — find one date that works."""

    ROUNDTABLE = "roundtable"
    """Ask your Advisor — collect and synthesise opinions."""

    ALL = (SCHEDULE, ROUNDTABLE)


class DateKind:
    """The six kinds of date from the product concept.

    Stage 1 implements ``DAY_SLOTS`` and ``WHOLE_DAY``; the other four are
    declared here because they are part of the concept and because the slot
    table already holds their shape.
    """

    DAY_SLOTS = "day_slots"
    """Chosen days, one or more time slots per day."""

    WHOLE_DAY = "whole_day"
    """Chosen days, no time of day."""

    WEEK = "week"          # stage 2
    MONTH = "month"        # stage 2
    SPAN = "span"          # stage 2 — several consecutive days as one slot
    WEEKLY = "weekly"      # stage 2 — a recurring weekday

    IMPLEMENTED = (DAY_SLOTS, WHOLE_DAY)
    ALL = (DAY_SLOTS, WHOLE_DAY, WEEK, MONTH, SPAN, WEEKLY)


class ChannelKind:
    PHONE = "phone"
    EMAIL = "email"        # stage 2
    ALL = (PHONE, EMAIL)


class ProjectState:
    DRAFT = "draft"
    ASKING = "asking"
    DECIDED = "decided"
    INVITED = "invited"


class RoundKind:
    """Which conversation a poll of a project represents."""

    AVAILABILITY = "availability"
    ROUNDTABLE = "roundtable"     # stage 2
    INVITATION = "invitation"
    ALL = (AVAILABILITY, ROUNDTABLE, INVITATION)


WEEKDAYS: dict[str, tuple[str, ...]] = {
    "de": ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"),
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
}

_ALL_DAY_WORD = {"de": "ganztägig", "en": "all day"}


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------

PROJECT_SCHEMA = """
CREATE TABLE IF NOT EXISTS contact (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    note          TEXT NOT NULL DEFAULT '',
    photo_blob    BLOB,
    photo_mime    TEXT,
    -- stage 3: where this contact was imported from. Empty until connectors exist.
    source_connector_id TEXT,
    external_id   TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contact_channel (
    id          TEXT PRIMARY KEY,
    contact_id  TEXT NOT NULL REFERENCES contact(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    value       TEXT NOT NULL,
    position    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS contact_group (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contact_group_member (
    group_id    TEXT NOT NULL REFERENCES contact_group(id) ON DELETE CASCADE,
    contact_id  TEXT NOT NULL REFERENCES contact(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (group_id, contact_id)
);

CREATE TABLE IF NOT EXISTS project (
    id            TEXT PRIMARY KEY,
    occasion      TEXT NOT NULL,
    mode          TEXT NOT NULL DEFAULT 'schedule',
    date_kind     TEXT NOT NULL DEFAULT 'day_slots',
    organizer     TEXT NOT NULL,
    language      TEXT NOT NULL DEFAULT 'de',
    region        TEXT NOT NULL DEFAULT 'DE',
    locale        TEXT NOT NULL DEFAULT 'de-DE',
    state         TEXT NOT NULL DEFAULT 'draft',
    group_id      TEXT REFERENCES contact_group(id) ON DELETE SET NULL,
    -- How pressing this is, in the organizer's own words ("wirklich dringend").
    -- Changes the tone of the call, not the flow. Stage 2 also uses it to
    -- decide who gets called first.
    urgency       TEXT NOT NULL DEFAULT '',
    fixture_name  TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_slot (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL DEFAULT 0,
    day_date    TEXT,
    end_date    TEXT,
    weekday     INTEGER,
    start_time  TEXT,
    end_time    TEXT,
    all_day     INTEGER NOT NULL DEFAULT 0,
    label       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_invitee (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    contact_id  TEXT NOT NULL REFERENCES contact(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (project_id, contact_id)
);

CREATE TABLE IF NOT EXISTS phrase (
    id          TEXT PRIMARY KEY,
    scope       TEXT NOT NULL DEFAULT 'project',
    scope_id    TEXT,
    kind        TEXT NOT NULL,
    text        TEXT NOT NULL,
    position    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS project_question (
    id          TEXT PRIMARY KEY,
    scope       TEXT NOT NULL DEFAULT 'project',
    scope_id    TEXT,
    text        TEXT NOT NULL,
    position    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS project_criteria (
    project_id        TEXT PRIMARY KEY REFERENCES project(id) ON DELETE CASCADE,
    favourite_slot_id TEXT,
    min_count         INTEGER,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_must_have (
    project_id  TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    contact_id  TEXT NOT NULL REFERENCES contact(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, contact_id)
);

CREATE TABLE IF NOT EXISTS decision (
    project_id  TEXT PRIMARY KEY REFERENCES project(id) ON DELETE CASCADE,
    slot_id     TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    decided_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS connector (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    label       TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    enabled     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_channel_contact ON contact_channel(contact_id);
CREATE INDEX IF NOT EXISTS idx_slot_project ON project_slot(project_id);
CREATE INDEX IF NOT EXISTS idx_invitee_project ON project_invitee(project_id);
CREATE INDEX IF NOT EXISTS idx_phrase_scope ON phrase(scope, scope_id);
"""

_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    # (table, column, definition) — appended to databases written before the
    # column existed. Added on 2026-08-02 when ABLAUF.md node B3 turned out to
    # have no home in the model.
    ("project", "urgency", "TEXT NOT NULL DEFAULT ''"),
    ("project_question", "kind", "TEXT NOT NULL DEFAULT 'open'"),
    ("project_question", "options_json", "TEXT NOT NULL DEFAULT '[]'"),
)


# --------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Channel:
    id: str
    contact_id: str
    kind: str
    value: str
    position: int = 0

    @property
    def masked(self) -> str:
        return mask(self.value) if self.kind == ChannelKind.PHONE else _mask_email(self.value)


@dataclass(frozen=True)
class Contact:
    """One person in the local address book."""

    id: str
    name: str
    note: str = ""
    photo_mime: str | None = None
    has_photo: bool = False
    created_at: str = ""
    channels: tuple[Channel, ...] = ()

    @property
    def phone(self) -> str | None:
        """The number to dial, or ``None`` when there is none.

        ``None`` here is what "cannot be called at all" means everywhere else —
        the fourth state of the result view lives on this property.
        """
        for channel in self.channels:
            if channel.kind == ChannelKind.PHONE and channel.value.strip():
                return channel.value
        return None

    @property
    def email(self) -> str | None:
        for channel in self.channels:
            if channel.kind == ChannelKind.EMAIL and channel.value.strip():
                return channel.value
        return None

    @property
    def callable(self) -> bool:
        return self.phone is not None

    @property
    def phone_masked(self) -> str:
        phone = self.phone
        return mask(phone) if phone else "—"

    @property
    def given_name(self) -> str:
        return self.name.strip().split()[0] if self.name.strip() else self.name

    @property
    def initials(self) -> str:
        parts = [part for part in self.name.strip().split() if part]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()


@dataclass(frozen=True)
class ContactGroup:
    """A reusable, freely named audience such as Family or Tennisclub."""

    id: str
    name: str
    note: str = ""
    created_at: str = ""
    members: tuple[Contact, ...] = ()


@dataclass(frozen=True)
class ProjectQuestion:
    """One advisor question and the answer shape it asks CALL-E to fill."""

    id: str
    text: str
    kind: str = "open"
    options: tuple[str, ...] = ()
    scope: str = "project"
    scope_id: str | None = None
    position: int = 0


@dataclass(frozen=True)
class Project:
    id: str
    occasion: str
    mode: str = ProjectMode.SCHEDULE
    date_kind: str = DateKind.DAY_SLOTS
    organizer: str = ""
    language: str = "de"
    region: str = "DE"
    locale: str = "de-DE"
    state: str = ProjectState.DRAFT
    group_id: str | None = None
    urgency: str = ""
    """How pressing it is, in the organizer's own words. Changes the tone of
    the call, never the flow — an urgent question is still asked once and still
    accepts a refusal."""

    fixture_name: str | None = None
    created_at: str = ""

    @property
    def is_german(self) -> bool:
        return str(self.language).lower().startswith("de")


@dataclass(frozen=True)
class Slot:
    """One candidate date. The shape covers all six kinds of date."""

    id: str
    project_id: str
    label: str
    position: int = 0
    day_date: str | None = None
    end_date: str | None = None
    weekday: int | None = None
    start_time: str | None = None
    end_time: str | None = None
    all_day: bool = False

    @property
    def day(self) -> date | None:
        return _parse_date(self.day_date)

    @property
    def time_range(self) -> str:
        if self.all_day or not self.start_time:
            return ""
        return f"{self.start_time}–{self.end_time}" if self.end_time else self.start_time


@dataclass(frozen=True)
class Invitee:
    id: str
    project_id: str
    contact_id: str
    position: int = 0
    contact: Contact | None = None

    @property
    def name(self) -> str:
        return self.contact.name if self.contact else self.contact_id

    @property
    def callable(self) -> bool:
        return bool(self.contact and self.contact.callable)


@dataclass(frozen=True)
class Phrase:
    id: str
    kind: str
    text: str
    scope: str = "project"
    scope_id: str | None = None
    position: int = 0


@dataclass(frozen=True)
class Criteria:
    """What makes a slot a good slot, for this project.

    All three are optional. The score is reported as "met of *configured*", so
    a person who only names a favourite date sees "1 von 1" and not "1 von 3".
    """

    project_id: str
    favourite_slot_id: str | None = None
    min_count: int | None = None
    must_have: tuple[str, ...] = ()
    updated_at: str = ""

    @property
    def configured(self) -> int:
        return sum(
            1
            for value in (self.favourite_slot_id, self.min_count or None, self.must_have or None)
            if value
        )

    @property
    def is_empty(self) -> bool:
        return self.configured == 0


@dataclass(frozen=True)
class Decision:
    project_id: str
    slot_id: str
    note: str = ""
    decided_at: str = ""


# --------------------------------------------------------------------------
# labels
# --------------------------------------------------------------------------


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _weekday_name(day: date, language: str) -> str:
    names = WEEKDAYS["de"] if str(language).lower().startswith("de") else WEEKDAYS["en"]
    return names[day.weekday()]


def slot_label(
    *,
    language: str = "de",
    day_date: str | None = None,
    end_date: str | None = None,
    weekday: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    all_day: bool = False,
) -> str:
    """The canonical wording of a slot.

    This string does three jobs at once, which is why it is generated in exactly
    one place: it is shown in the calendar, it is **spoken by the voice agent**,
    and it is what comes back in ``available_slots`` and gets matched by
    :mod:`ringedingeding.merge`. If the label drifts, the calendar and the
    result stop agreeing with each other.
    """
    german = str(language).lower().startswith("de")
    day = _parse_date(day_date)
    parts: list[str] = []

    if day is not None:
        parts.append(f"{_weekday_name(day, language)} {day.day:02d}.{day.month:02d}.")
        end = _parse_date(end_date)
        if end is not None and end != day:
            parts.append(f"– {_weekday_name(end, language)} {end.day:02d}.{end.month:02d}.")
    elif weekday is not None:
        names = WEEKDAYS["de"] if german else WEEKDAYS["en"]
        every = "jeden" if german else "every"
        parts.append(f"{every} {names[max(0, min(6, int(weekday)))]}")

    if all_day or not start_time:
        parts.append(_ALL_DAY_WORD["de" if german else "en"])
    else:
        parts.append(f"{start_time}-{end_time}" if end_time else start_time)

    return " ".join(part for part in parts if part).strip()


def _mask_email(value: str) -> str:
    """Show that there is an address without showing it."""
    text = str(value or "")
    if "@" not in text:
        return "***"
    local, _, domain = text.partition("@")
    head = local[:1] or "*"
    return f"{head}***@{domain}"


# --------------------------------------------------------------------------
# store
# --------------------------------------------------------------------------


class ProjectStore:
    """Reads and writes the project layer of one database.

    Wraps a :class:`~ringedingeding.store.Store` rather than replacing it: the
    call machinery keeps using ``poll``/``participant``/``answer`` exactly as
    before, and this class only adds what sits above.
    """

    def __init__(self, store: Store) -> None:
        self.store = store
        self.connection: sqlite3.Connection = store.connection
        self.connection.executescript(PROJECT_SCHEMA)
        self._add_missing_columns()
        self.connection.commit()

    def _add_missing_columns(self) -> None:
        """Bring a database written by an earlier version up to date.

        ``CREATE TABLE IF NOT EXISTS`` does nothing to a table that already
        exists, so a column added later has to be appended explicitly — the same
        rule, and the same one-way discipline, as in
        :class:`ringedingeding.store.Store`: things are added, never dropped or
        rewritten.
        """
        for table, column, definition in _ADDED_COLUMNS:
            existing = {
                row["name"]
                for row in self.connection.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if existing and column not in existing:
                self.connection.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                )

    # -- contacts -----------------------------------------------------------

    def create_contact(
        self,
        *,
        name: str,
        phone: str | None = None,
        email: str | None = None,
        note: str = "",
        photo: tuple[bytes, str] | None = None,
        contact_id: str | None = None,
    ) -> Contact:
        """Add a contact. An invalid number is rejected before anything is stored.

        Validated up front rather than while writing the channel: a rejected
        number used to leave a nameless half-contact behind, which then showed
        up in the address book as somebody who could not be called.
        """
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("a contact needs a name")
        if phone and phone.strip():
            normalize_e164(phone)
        if email and email.strip() and "@" not in email:
            raise ValueError(f"{email!r} does not look like an e-mail address")
        identifier = contact_id or new_id("c")
        blob, mime = (photo or (None, None))
        self.connection.execute(
            "INSERT INTO contact (id, name, note, photo_blob, photo_mime, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (identifier, clean_name, note.strip(), blob, mime, utc_now()),
        )
        self.connection.commit()
        if phone and phone.strip():
            self.set_channel(identifier, ChannelKind.PHONE, phone)
        if email and email.strip():
            self.set_channel(identifier, ChannelKind.EMAIL, email)
        return self.contact(identifier)

    def set_channel(self, contact_id: str, kind: str, value: str) -> Channel:
        """Set (or replace) one channel of a contact.

        Phone numbers are normalised to E.164 here — the earliest point at which
        a number exists in this program, and therefore the right place to refuse
        one that could never be dialed.
        """
        if kind not in ChannelKind.ALL:
            raise ValueError(f"unknown channel kind {kind!r}")
        text = str(value or "").strip()
        if not text:
            raise ValueError("a channel needs a value")
        if kind == ChannelKind.PHONE:
            text = normalize_e164(text)
        elif "@" not in text:
            raise ValueError(f"{text!r} does not look like an e-mail address")

        self.connection.execute(
            "DELETE FROM contact_channel WHERE contact_id = ? AND kind = ?", (contact_id, kind)
        )
        channel = Channel(id=new_id("ch"), contact_id=contact_id, kind=kind, value=text)
        self.connection.execute(
            "INSERT INTO contact_channel (id, contact_id, kind, value, position) VALUES (?,?,?,?,?)",
            (channel.id, channel.contact_id, channel.kind, channel.value, channel.position),
        )
        self.connection.commit()
        return channel

    def remove_channel(self, contact_id: str, kind: str) -> None:
        self.connection.execute(
            "DELETE FROM contact_channel WHERE contact_id = ? AND kind = ?", (contact_id, kind)
        )
        self.connection.commit()

    def update_contact(
        self, contact_id: str, *, name: str | None = None, note: str | None = None
    ) -> Contact:
        if name is not None and name.strip():
            self.connection.execute(
                "UPDATE contact SET name = ? WHERE id = ?", (name.strip(), contact_id)
            )
        if note is not None:
            self.connection.execute(
                "UPDATE contact SET note = ? WHERE id = ?", (note.strip(), contact_id)
            )
        self.connection.commit()
        return self.contact(contact_id)

    def set_photo(self, contact_id: str, blob: bytes, mime: str) -> None:
        self.connection.execute(
            "UPDATE contact SET photo_blob = ?, photo_mime = ? WHERE id = ?",
            (sqlite3.Binary(blob), mime, contact_id),
        )
        self.connection.commit()

    def photo(self, contact_id: str) -> tuple[bytes, str] | None:
        row = self.connection.execute(
            "SELECT photo_blob, photo_mime FROM contact WHERE id = ?", (contact_id,)
        ).fetchone()
        if row is None or row["photo_blob"] is None:
            return None
        return bytes(row["photo_blob"]), str(row["photo_mime"] or "image/png")

    def delete_contact(self, contact_id: str) -> None:
        self.connection.execute("DELETE FROM contact WHERE id = ?", (contact_id,))
        self.connection.commit()

    def contact(self, contact_id: str) -> Contact:
        row = self.connection.execute(
            "SELECT * FROM contact WHERE id = ?", (contact_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no contact with id {contact_id!r}")
        return self._contact_from_row(row)

    def contacts(self) -> list[Contact]:
        rows = self.connection.execute("SELECT * FROM contact ORDER BY name COLLATE NOCASE").fetchall()
        return [self._contact_from_row(row) for row in rows]

    def _contact_from_row(self, row: sqlite3.Row) -> Contact:
        channels = tuple(
            Channel(
                id=channel["id"],
                contact_id=channel["contact_id"],
                kind=channel["kind"],
                value=channel["value"],
                position=channel["position"],
            )
            for channel in self.connection.execute(
                "SELECT * FROM contact_channel WHERE contact_id = ? ORDER BY position, rowid",
                (row["id"],),
            ).fetchall()
        )
        return Contact(
            id=row["id"],
            name=row["name"],
            note=row["note"] or "",
            photo_mime=row["photo_mime"],
            has_photo=row["photo_blob"] is not None,
            created_at=row["created_at"] or "",
            channels=channels,
        )

    # -- projects -----------------------------------------------------------

    def create_project(
        self,
        *,
        occasion: str,
        organizer: str,
        mode: str = ProjectMode.SCHEDULE,
        date_kind: str = DateKind.DAY_SLOTS,
        language: str = "de",
        region: str = "DE",
        locale: str = "de-DE",
        urgency: str = "",
        group_id: str | None = None,
        fixture_name: str | None = None,
        project_id: str | None = None,
    ) -> Project:
        if not occasion.strip():
            raise ValueError("a project needs an occasion — what is it about?")
        if mode not in ProjectMode.ALL:
            raise ValueError(f"unknown project mode {mode!r}")
        if date_kind not in DateKind.ALL:
            raise ValueError(f"unknown date kind {date_kind!r}")
        if date_kind not in DateKind.IMPLEMENTED:
            raise ValueError(
                f"date kind {date_kind!r} is part of the concept but not built yet "
                f"(stage 2). Available now: {', '.join(DateKind.IMPLEMENTED)}."
            )
        project = Project(
            id=project_id or new_id("prj"),
            occasion=occasion.strip(),
            mode=mode,
            date_kind=date_kind,
            organizer=organizer.strip(),
            language=language,
            region=region,
            locale=locale,
            state=ProjectState.DRAFT,
            urgency=urgency.strip(),
            group_id=group_id,
            fixture_name=fixture_name,
            created_at=utc_now(),
        )
        self.connection.execute(
            "INSERT INTO project (id, occasion, mode, date_kind, organizer, language, region,"
            " locale, state, group_id, urgency, fixture_name, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                project.id,
                project.occasion,
                project.mode,
                project.date_kind,
                project.organizer,
                project.language,
                project.region,
                project.locale,
                project.state,
                project.group_id,
                project.urgency,
                project.fixture_name,
                project.created_at,
            ),
        )
        self.connection.commit()
        return project

    # -- groups -------------------------------------------------------------

    def create_group(
        self,
        *,
        name: str,
        contact_ids: Sequence[str] = (),
        note: str = "",
        group_id: str | None = None,
    ) -> ContactGroup:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("a group needs a name")
        identifier = group_id or new_id("grp")
        self.connection.execute(
            "INSERT INTO contact_group (id, name, note, created_at) VALUES (?,?,?,?)",
            (identifier, clean_name, note.strip(), utc_now()),
        )
        self.connection.commit()
        self.set_group_members(identifier, contact_ids)
        return self.group(identifier)

    def set_group_members(
        self, group_id: str, contact_ids: Sequence[str]
    ) -> ContactGroup:
        self.connection.execute(
            "DELETE FROM contact_group_member WHERE group_id = ?", (group_id,)
        )
        seen: set[str] = set()
        rows: list[tuple[str, str, int]] = []
        for contact_id in contact_ids:
            if contact_id in seen:
                continue
            # Fail before committing a half-valid group.
            self.contact(contact_id)
            seen.add(contact_id)
            rows.append((group_id, contact_id, len(rows)))
        self.connection.executemany(
            "INSERT INTO contact_group_member (group_id, contact_id, position) VALUES (?,?,?)",
            rows,
        )
        self.connection.commit()
        return self.group(group_id)

    def group(self, group_id: str) -> ContactGroup:
        row = self.connection.execute(
            "SELECT * FROM contact_group WHERE id = ?", (group_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no group with id {group_id!r}")
        members = tuple(
            self.contact(member["contact_id"])
            for member in self.connection.execute(
                "SELECT contact_id FROM contact_group_member WHERE group_id = ?"
                " ORDER BY position, rowid",
                (group_id,),
            ).fetchall()
        )
        return ContactGroup(
            id=row["id"],
            name=row["name"],
            note=row["note"] or "",
            created_at=row["created_at"] or "",
            members=members,
        )

    def groups(self) -> list[ContactGroup]:
        rows = self.connection.execute(
            "SELECT id FROM contact_group ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return [self.group(row["id"]) for row in rows]

    def delete_group(self, group_id: str) -> None:
        self.connection.execute("DELETE FROM contact_group WHERE id = ?", (group_id,))
        self.connection.commit()

    # -- advisor questions -------------------------------------------------

    def set_questions(
        self,
        texts: Sequence[str],
        *,
        kind: str = "open",
        options: Sequence[str] = (),
        scope: str = "project",
        scope_id: str | None = None,
    ) -> list[ProjectQuestion]:
        if kind not in ("open", "choice"):
            raise ValueError(f"unknown question kind {kind!r}")
        clean_options = tuple(dict.fromkeys(str(value).strip() for value in options if str(value).strip()))
        if kind == "choice" and len(clean_options) < 2:
            raise ValueError("a choice question needs at least two distinct options")
        self.connection.execute(
            "DELETE FROM project_question WHERE scope = ? AND scope_id IS ?",
            (scope, scope_id),
        )
        questions = [
            ProjectQuestion(
                id=new_id("q"),
                text=str(value).strip(),
                kind=kind,
                options=clean_options,
                scope=scope,
                scope_id=scope_id,
                position=position,
            )
            for position, value in enumerate(texts)
            if str(value).strip()
        ]
        self.connection.executemany(
            "INSERT INTO project_question"
            " (id, scope, scope_id, text, position, kind, options_json)"
            " VALUES (?,?,?,?,?,?,?)",
            [
                (
                    question.id,
                    question.scope,
                    question.scope_id,
                    question.text,
                    question.position,
                    question.kind,
                    json.dumps(list(question.options), ensure_ascii=False),
                )
                for question in questions
            ],
        )
        self.connection.commit()
        return questions

    def questions(
        self, *, scope: str = "project", scope_id: str | None = None
    ) -> list[ProjectQuestion]:
        rows = self.connection.execute(
            "SELECT * FROM project_question WHERE scope = ? AND scope_id IS ?"
            " ORDER BY position, rowid",
            (scope, scope_id),
        ).fetchall()
        return [
            ProjectQuestion(
                id=row["id"],
                text=row["text"],
                kind=(row["kind"] or "open") if "kind" in row.keys() else "open",
                options=tuple(json.loads(row["options_json"] or "[]"))
                if "options_json" in row.keys()
                else (),
                scope=row["scope"],
                scope_id=row["scope_id"],
                position=row["position"],
            )
            for row in rows
        ]

    def project(self, project_id: str) -> Project:
        row = self.connection.execute(
            "SELECT * FROM project WHERE id = ?", (project_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no project with id {project_id!r}")
        return _project_from_row(row)

    def projects(self) -> list[Project]:
        rows = self.connection.execute(
            "SELECT * FROM project ORDER BY created_at DESC"
        ).fetchall()
        return [_project_from_row(row) for row in rows]

    def set_state(self, project_id: str, state: str) -> None:
        self.connection.execute(
            "UPDATE project SET state = ? WHERE id = ?", (state, project_id)
        )
        self.connection.commit()

    def delete_project(self, project_id: str) -> None:
        self.connection.execute("DELETE FROM project WHERE id = ?", (project_id,))
        self.connection.commit()

    # -- slots --------------------------------------------------------------

    def replace_slots(self, project: Project, specs: Sequence[dict[str, Any]]) -> list[Slot]:
        """Set the whole candidate list at once.

        Replacing rather than patching keeps the labels and the ordering in one
        transaction. Answers already given are keyed by label, so a slot that
        survives the replacement keeps its answers.
        """
        self.connection.execute("DELETE FROM project_slot WHERE project_id = ?", (project.id,))
        slots: list[Slot] = []
        for position, spec in enumerate(specs):
            all_day = bool(spec.get("all_day"))
            start_time = _clean_time(spec.get("start_time")) if not all_day else None
            end_time = _clean_time(spec.get("end_time")) if not all_day else None
            if start_time and end_time and end_time <= start_time:
                raise ValueError(
                    f"slot on {spec.get('day_date')} ends at {end_time}, "
                    f"which is not after {start_time}"
                )
            label = str(spec.get("label") or "").strip() or slot_label(
                language=project.language,
                day_date=spec.get("day_date"),
                end_date=spec.get("end_date"),
                weekday=spec.get("weekday"),
                start_time=start_time,
                end_time=end_time,
                all_day=all_day,
            )
            slot = Slot(
                id=spec.get("id") or new_id("slot"),
                project_id=project.id,
                label=label,
                position=position,
                day_date=spec.get("day_date"),
                end_date=spec.get("end_date"),
                weekday=spec.get("weekday"),
                start_time=start_time,
                end_time=end_time,
                all_day=all_day,
            )
            slots.append(slot)

        labels = [slot.label for slot in slots]
        duplicates = {label for label in labels if labels.count(label) > 1}
        if duplicates:
            raise ValueError(
                "two candidate dates would be spoken identically: "
                + ", ".join(sorted(duplicates))
                + ". The voice agent could not tell them apart."
            )

        self.connection.executemany(
            "INSERT INTO project_slot (id, project_id, position, day_date, end_date, weekday,"
            " start_time, end_time, all_day, label) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    slot.id,
                    slot.project_id,
                    slot.position,
                    slot.day_date,
                    slot.end_date,
                    slot.weekday,
                    slot.start_time,
                    slot.end_time,
                    int(slot.all_day),
                    slot.label,
                )
                for slot in slots
            ],
        )
        self.connection.commit()
        return slots

    def slots(self, project_id: str) -> list[Slot]:
        rows = self.connection.execute(
            "SELECT * FROM project_slot WHERE project_id = ? ORDER BY position, rowid",
            (project_id,),
        ).fetchall()
        return [_slot_from_row(row) for row in rows]

    # -- invitees -----------------------------------------------------------

    def set_invitees(self, project_id: str, contact_ids: Sequence[str]) -> list[Invitee]:
        self.connection.execute(
            "DELETE FROM project_invitee WHERE project_id = ?", (project_id,)
        )
        seen: set[str] = set()
        rows: list[tuple[Any, ...]] = []
        position = 0
        for contact_id in contact_ids:
            if contact_id in seen:
                continue
            seen.add(contact_id)
            rows.append((new_id("inv"), project_id, contact_id, position))
            position += 1
        self.connection.executemany(
            "INSERT INTO project_invitee (id, project_id, contact_id, position) VALUES (?,?,?,?)",
            rows,
        )
        self.connection.commit()
        return self.invitees(project_id)

    def invitees(self, project_id: str) -> list[Invitee]:
        rows = self.connection.execute(
            "SELECT * FROM project_invitee WHERE project_id = ? ORDER BY position, rowid",
            (project_id,),
        ).fetchall()
        out: list[Invitee] = []
        for row in rows:
            try:
                contact = self.contact(row["contact_id"])
            except KeyError:
                contact = None
            out.append(
                Invitee(
                    id=row["id"],
                    project_id=row["project_id"],
                    contact_id=row["contact_id"],
                    position=row["position"],
                    contact=contact,
                )
            )
        return out

    # -- phrases ------------------------------------------------------------

    def set_phrases(
        self, kind: str, texts: Sequence[str], *, scope: str = "project", scope_id: str | None = None
    ) -> list[Phrase]:
        self.connection.execute(
            "DELETE FROM phrase WHERE kind = ? AND scope = ? AND scope_id IS ?",
            (kind, scope, scope_id),
        )
        phrases = [
            Phrase(
                id=new_id("ph"),
                kind=kind,
                text=text.strip(),
                scope=scope,
                scope_id=scope_id,
                position=position,
            )
            for position, text in enumerate(texts)
            if text and text.strip()
        ]
        self.connection.executemany(
            "INSERT INTO phrase (id, scope, scope_id, kind, text, position) VALUES (?,?,?,?,?,?)",
            [(p.id, p.scope, p.scope_id, p.kind, p.text, p.position) for p in phrases],
        )
        self.connection.commit()
        return phrases

    def phrases(
        self, kind: str, *, scope: str = "project", scope_id: str | None = None
    ) -> list[Phrase]:
        rows = self.connection.execute(
            "SELECT * FROM phrase WHERE kind = ? AND scope = ? AND scope_id IS ?"
            " ORDER BY position, rowid",
            (kind, scope, scope_id),
        ).fetchall()
        return [
            Phrase(
                id=row["id"],
                kind=row["kind"],
                text=row["text"],
                scope=row["scope"],
                scope_id=row["scope_id"],
                position=row["position"],
            )
            for row in rows
        ]

    # -- criteria and decision ----------------------------------------------

    def set_criteria(
        self,
        project_id: str,
        *,
        favourite_slot_id: str | None = None,
        min_count: int | None = None,
        must_have: Sequence[str] = (),
    ) -> Criteria:
        self.connection.execute(
            "INSERT INTO project_criteria (project_id, favourite_slot_id, min_count, updated_at)"
            " VALUES (?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET"
            " favourite_slot_id=excluded.favourite_slot_id, min_count=excluded.min_count,"
            " updated_at=excluded.updated_at",
            (project_id, favourite_slot_id or None, min_count, utc_now()),
        )
        self.connection.execute(
            "DELETE FROM project_must_have WHERE project_id = ?", (project_id,)
        )
        self.connection.executemany(
            "INSERT OR IGNORE INTO project_must_have (project_id, contact_id) VALUES (?,?)",
            [(project_id, contact_id) for contact_id in must_have if contact_id],
        )
        self.connection.commit()
        return self.criteria(project_id)

    def criteria(self, project_id: str) -> Criteria:
        row = self.connection.execute(
            "SELECT * FROM project_criteria WHERE project_id = ?", (project_id,)
        ).fetchone()
        must_have = tuple(
            entry["contact_id"]
            for entry in self.connection.execute(
                "SELECT contact_id FROM project_must_have WHERE project_id = ?", (project_id,)
            ).fetchall()
        )
        if row is None:
            return Criteria(project_id=project_id, must_have=must_have)
        return Criteria(
            project_id=project_id,
            favourite_slot_id=row["favourite_slot_id"],
            min_count=row["min_count"],
            must_have=must_have,
            updated_at=row["updated_at"] or "",
        )

    def set_decision(self, project_id: str, slot_id: str, note: str = "") -> Decision:
        decision = Decision(
            project_id=project_id, slot_id=slot_id, note=note.strip(), decided_at=utc_now()
        )
        self.connection.execute(
            "INSERT INTO decision (project_id, slot_id, note, decided_at) VALUES (?,?,?,?)"
            " ON CONFLICT(project_id) DO UPDATE SET slot_id=excluded.slot_id,"
            " note=excluded.note, decided_at=excluded.decided_at",
            (decision.project_id, decision.slot_id, decision.note, decision.decided_at),
        )
        self.connection.commit()
        self.set_state(project_id, ProjectState.DECIDED)
        return decision

    def decision(self, project_id: str) -> Decision | None:
        row = self.connection.execute(
            "SELECT * FROM decision WHERE project_id = ?", (project_id,)
        ).fetchone()
        if row is None:
            return None
        return Decision(
            project_id=row["project_id"],
            slot_id=row["slot_id"],
            note=row["note"] or "",
            decided_at=row["decided_at"] or "",
        )

    def clear_decision(self, project_id: str) -> None:
        self.connection.execute("DELETE FROM decision WHERE project_id = ?", (project_id,))
        self.connection.commit()

    # -- rounds (polls belonging to a project) -------------------------------

    def round_ids(self, project_id: str, round_kind: str) -> list[str]:
        rows = self.connection.execute(
            "SELECT id FROM poll WHERE project_id = ? AND round_kind = ? ORDER BY created_at",
            (project_id, round_kind),
        ).fetchall()
        return [row["id"] for row in rows]


def _clean_time(value: Any) -> str | None:
    """Accept ``"14:00"``, ``"14"``, ``"9:5"`` — reject anything else."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    parts = text.split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 and parts[1] != "" else 0
        return time(hour=hour, minute=minute).strftime("%H:%M")
    except (ValueError, IndexError):
        raise ValueError(f"{text!r} is not a time of day (expected something like 14:00)") from None


def _project_from_row(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        occasion=row["occasion"],
        mode=row["mode"],
        date_kind=row["date_kind"],
        organizer=row["organizer"],
        language=row["language"],
        region=row["region"],
        locale=row["locale"],
        state=row["state"],
        group_id=row["group_id"],
        urgency=(row["urgency"] or "") if "urgency" in row.keys() else "",
        fixture_name=row["fixture_name"],
        created_at=row["created_at"] or "",
    )


def _slot_from_row(row: sqlite3.Row) -> Slot:
    return Slot(
        id=row["id"],
        project_id=row["project_id"],
        label=row["label"],
        position=row["position"],
        day_date=row["day_date"],
        end_date=row["end_date"],
        weekday=row["weekday"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        all_day=bool(row["all_day"]),
    )
