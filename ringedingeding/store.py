"""SQLite persistence.

State is written the moment an outcome arrives rather than at the end of the
run. That is what makes Ctrl-C harmless: whatever calls finished are recorded,
the rest stay ``PENDING``, and a later run picks up exactly there.

The database holds phone numbers because you cannot dial a mask. Everything
else leans towards the local reference (``ref``) instead of personal data, and
no output path ever prints the raw number — see :mod:`ringedingeding.phone`.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from .huckepack_storage import open_connection
from .locales import region_locale_for
from .models import (
    Answer,
    CallStatus,
    Participant,
    ParticipantState,
    Poll,
    PollKind,
    new_id,
)
from .server_mode import current_mode

__all__ = ["Store", "utc_now", "DEFAULT_DB_PATH"]

DEFAULT_DB_PATH = Path("ringedingeding.db")

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS poll (
    id           TEXT PRIMARY KEY,
    question     TEXT NOT NULL,
    kind         TEXT NOT NULL,
    organizer    TEXT NOT NULL,
    language     TEXT NOT NULL DEFAULT 'en',
    region       TEXT NOT NULL DEFAULT 'US',
    locale       TEXT NOT NULL DEFAULT 'en-US',
    options_json TEXT NOT NULL DEFAULT '[]',
    window_json  TEXT NOT NULL DEFAULT '[]',
    created_at   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'open',
    -- Set when this poll is one round of a project (see ringedingeding.projects).
    -- Null for a poll created straight from the command line.
    project_id   TEXT,
    round_kind   TEXT,
    simulated    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS participant (
    id           TEXT PRIMARY KEY,
    poll_id      TEXT NOT NULL REFERENCES poll(id) ON DELETE CASCADE,
    ref          TEXT NOT NULL,
    name         TEXT NOT NULL,
    phone_e164   TEXT NOT NULL,
    state        TEXT NOT NULL DEFAULT 'pending',
    call_run_id  TEXT,
    attempted_at TEXT,
    -- Back-reference to the address book, when the poll came from a project.
    contact_id   TEXT,
    UNIQUE (poll_id, ref)
);

CREATE TABLE IF NOT EXISTS answer (
    participant_id  TEXT PRIMARY KEY REFERENCES participant(id) ON DELETE CASCADE,
    call_status     TEXT NOT NULL,
    structured_json TEXT NOT NULL DEFAULT '{}',
    raw_text        TEXT NOT NULL DEFAULT '',
    transcript      TEXT NOT NULL DEFAULT '',
    received_at     TEXT NOT NULL,
    run_id          TEXT,
    error           TEXT
);

CREATE INDEX IF NOT EXISTS idx_participant_poll ON participant(poll_id);
"""

_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    # (table, column, definition) — appended to databases written by an
    # earlier version. Adding a column is the only migration this project
    # performs; nothing is ever dropped or rewritten.
    ("answer", "transcript", "TEXT NOT NULL DEFAULT ''"),
    ("poll", "project_id", "TEXT"),
    ("poll", "round_kind", "TEXT"),
    ("poll", "simulated", "INTEGER NOT NULL DEFAULT 0"),
    ("participant", "contact_id", "TEXT"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PollNotFound(KeyError):
    """No poll with that id."""


class Store:
    """Thin SQLite wrapper. All writes commit immediately."""

    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        # Where this database actually lives is the server mode's decision: the
        # file below, or the copy the browser sent for this session. In the
        # browser modes not even the directory is created — see
        # ``huckepack_storage``.
        if current_mode().stores_on_host:
            if self.path.parent and str(self.path.parent) not in ("", "."):
                self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = open_connection(str(self.path))
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(_SCHEMA)
        self._add_missing_columns()
        self.connection.commit()

    def _add_missing_columns(self) -> None:
        """Bring a database written by an older version up to date.

        ``CREATE TABLE IF NOT EXISTS`` does nothing to a table that already
        exists, so a new column has to be added explicitly — otherwise the
        first run after an update fails on somebody's saved poll.
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

    # -- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        try:
            self.connection.close()
        except sqlite3.ProgrammingError:
            pass

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- polls --------------------------------------------------------------

    def create_poll(
        self,
        *,
        question: str,
        kind: PollKind | str,
        organizer: str,
        language: str = "en",
        region: str | None = None,
        locale: str | None = None,
        options: Sequence[str] = (),
        slots: Sequence[str] = (),
        poll_id: str | None = None,
        project_id: str | None = None,
        round_kind: str | None = None,
        simulated: bool = False,
    ) -> Poll:
        parsed_kind = kind if isinstance(kind, PollKind) else PollKind.parse(kind)
        if parsed_kind is PollKind.CHOICE and not options:
            raise ValueError("a 'choice' poll needs at least two options")
        if parsed_kind is PollKind.CHOICE and len(set(options)) < 2:
            raise ValueError("a 'choice' poll needs at least two distinct options")
        region, locale = region_locale_for(language, region=region, locale=locale)

        poll = Poll(
            id=poll_id or new_id("poll"),
            question=question.strip(),
            kind=parsed_kind,
            organizer=organizer.strip(),
            language=language,
            region=region,
            locale=locale,
            options=tuple(options),
            slots=tuple(slots),
            created_at=utc_now(),
            status="open",
            project_id=project_id,
            round_kind=round_kind,
            simulated=bool(simulated),
        )
        self.connection.execute(
            "INSERT INTO poll (id, question, kind, organizer, language, region, locale,"
            " options_json, window_json, created_at, status, project_id, round_kind, simulated)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                poll.id,
                poll.question,
                poll.kind.value,
                poll.organizer,
                poll.language,
                poll.region,
                poll.locale,
                json.dumps(list(poll.options), ensure_ascii=False),
                json.dumps(list(poll.slots), ensure_ascii=False),
                poll.created_at,
                poll.status,
                poll.project_id,
                poll.round_kind,
                int(poll.simulated),
            ),
        )
        self.connection.commit()
        return poll

    def get_poll(self, poll_id: str) -> Poll:
        row = self.connection.execute("SELECT * FROM poll WHERE id = ?", (poll_id,)).fetchone()
        if row is None:
            raise PollNotFound(f"no poll with id {poll_id!r}")
        return _poll_from_row(row)

    def list_polls(self) -> list[Poll]:
        rows = self.connection.execute("SELECT * FROM poll ORDER BY created_at DESC").fetchall()
        return [_poll_from_row(row) for row in rows]

    def set_poll_status(self, poll_id: str, status: str) -> None:
        self.connection.execute("UPDATE poll SET status = ? WHERE id = ?", (status, poll_id))
        self.connection.commit()

    def set_poll_window(self, poll_id: str, slots: Sequence[str]) -> None:
        """Replace the proposed slots of a poll.

        The window is what the voice agent reads out *and* what the merge
        matches answers against, so it has to be rewritten whenever the project
        changes its candidate dates — otherwise the calendar and the answers
        stop describing the same thing.
        """
        self.connection.execute(
            "UPDATE poll SET window_json = ? WHERE id = ?",
            (json.dumps([str(slot) for slot in slots], ensure_ascii=False), poll_id),
        )
        self.connection.commit()

    def set_poll_question(self, poll_id: str, question: str) -> None:
        self.connection.execute(
            "UPDATE poll SET question = ? WHERE id = ?", (question.strip(), poll_id)
        )
        self.connection.commit()

    def set_poll_definition(
        self,
        poll_id: str,
        *,
        question: str,
        kind: PollKind | str,
        options: Sequence[str] = (),
    ) -> Poll:
        """Update an unrun advisor round without replacing its identity.

        A preview may create the round before the wording is final. Keeping the
        poll id preserves participants and links; answers, once present, are a
        fact and make changing the question unsafe.
        """
        if self.answers(poll_id):
            raise ValueError("a question with recorded answers cannot be changed")
        parsed = kind if isinstance(kind, PollKind) else PollKind.parse(kind)
        clean_options = tuple(
            dict.fromkeys(str(value).strip() for value in options if str(value).strip())
        )
        if parsed is PollKind.CHOICE and len(clean_options) < 2:
            raise ValueError("a 'choice' poll needs at least two distinct options")
        self.connection.execute(
            "UPDATE poll SET question = ?, kind = ?, options_json = ? WHERE id = ?",
            (
                question.strip(),
                parsed.value,
                json.dumps(list(clean_options), ensure_ascii=False),
                poll_id,
            ),
        )
        self.connection.commit()
        return self.get_poll(poll_id)

    def set_poll_simulated(self, poll_id: str, simulated: bool) -> None:
        """Mark (or unmark) a poll whose answers were invented locally."""
        self.connection.execute(
            "UPDATE poll SET simulated = ? WHERE id = ?", (int(bool(simulated)), poll_id)
        )
        self.connection.commit()

    # -- participants -------------------------------------------------------

    def add_participant(
        self,
        poll_id: str,
        *,
        name: str,
        phone: str,
        ref: str | None = None,
        contact_id: str | None = None,
    ) -> Participant:
        """Add one participant. The number is validated here, before storage."""
        existing = {row["ref"] for row in self._participant_rows(poll_id)}
        handle = (ref or _ref_from_name(name)).strip()
        candidate = handle
        suffix = 2
        while candidate in existing:
            candidate = f"{handle}{suffix}"
            suffix += 1

        participant = Participant(
            id=new_id("p"),
            poll_id=poll_id,
            ref=candidate,
            name=name.strip(),
            phone_e164=phone,  # validated in __post_init__
            contact_id=contact_id,
        )
        self.connection.execute(
            "INSERT INTO participant (id, poll_id, ref, name, phone_e164, state, contact_id)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                participant.id,
                participant.poll_id,
                participant.ref,
                participant.name,
                participant.phone_e164,
                participant.state.value,
                participant.contact_id,
            ),
        )
        self.connection.commit()
        return participant

    def _participant_rows(self, poll_id: str) -> list[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM participant WHERE poll_id = ? ORDER BY rowid", (poll_id,)
        ).fetchall()

    def participants(self, poll_id: str) -> list[Participant]:
        return [_participant_from_row(row) for row in self._participant_rows(poll_id)]

    def delete_participant(self, participant_id: str) -> None:
        """Remove a participant. Callers must check there is no answer first.

        Deleting cascades to ``answer``, which is why the only caller
        (:func:`ringedingeding.service.sync_participants`) refuses to remove
        anybody who has already given one.
        """
        self.connection.execute("DELETE FROM participant WHERE id = ?", (participant_id,))
        self.connection.commit()

    def mark_attempted(self, participant_id: str, run_id: str | None = None) -> None:
        self.connection.execute(
            "UPDATE participant SET attempted_at = ?, call_run_id = ? WHERE id = ?",
            (utc_now(), run_id, participant_id),
        )
        self.connection.commit()

    # -- answers ------------------------------------------------------------

    def record_answer(self, answer: Answer) -> None:
        """Insert or replace the answer for one participant."""
        self.connection.execute(
            "INSERT INTO answer (participant_id, call_status, structured_json, raw_text,"
            " transcript, received_at, run_id, error) VALUES (?,?,?,?,?,?,?,?)"
            " ON CONFLICT(participant_id) DO UPDATE SET"
            " call_status=excluded.call_status, structured_json=excluded.structured_json,"
            " raw_text=excluded.raw_text, transcript=excluded.transcript,"
            " received_at=excluded.received_at,"
            " run_id=excluded.run_id, error=excluded.error",
            (
                answer.participant_id,
                answer.call_status.value,
                json.dumps(answer.structured or {}, ensure_ascii=False),
                answer.raw_text or "",
                answer.transcript or "",
                answer.received_at or utc_now(),
                answer.run_id,
                answer.error,
            ),
        )
        self.connection.execute(
            "UPDATE participant SET state = ? WHERE id = ?",
            (ParticipantState.DONE.value, answer.participant_id),
        )
        self.connection.commit()

    def answers(self, poll_id: str) -> dict[str, Answer]:
        rows = self.connection.execute(
            "SELECT a.* FROM answer a JOIN participant p ON p.id = a.participant_id"
            " WHERE p.poll_id = ?",
            (poll_id,),
        ).fetchall()
        return {row["participant_id"]: _answer_from_row(row) for row in rows}

    def clear_answers(self, poll_id: str) -> int:
        """Drop all answers of a poll and reset participants to pending."""
        cursor = self.connection.execute(
            "DELETE FROM answer WHERE participant_id IN"
            " (SELECT id FROM participant WHERE poll_id = ?)",
            (poll_id,),
        )
        self.connection.execute(
            "UPDATE participant SET state = ?, attempted_at = NULL, call_run_id = NULL"
            " WHERE poll_id = ?",
            (ParticipantState.PENDING.value, poll_id),
        )
        self.connection.commit()
        return cursor.rowcount


def _ref_from_name(name: str) -> str:
    token = "".join(char for char in name.strip().lower() if char.isalnum() or char in "-_")
    return token[:16] or "person"


def _json_list(raw: Any) -> tuple[str, ...]:
    try:
        parsed = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return ()
    return tuple(str(item) for item in parsed) if isinstance(parsed, list) else ()


def _poll_from_row(row: sqlite3.Row) -> Poll:
    keys = row.keys()
    return Poll(
        id=row["id"],
        question=row["question"],
        kind=PollKind.parse(row["kind"]),
        organizer=row["organizer"],
        language=row["language"],
        region=row["region"],
        locale=row["locale"],
        options=_json_list(row["options_json"]),
        slots=_json_list(row["window_json"]),
        created_at=row["created_at"],
        status=row["status"],
        project_id=row["project_id"] if "project_id" in keys else None,
        round_kind=row["round_kind"] if "round_kind" in keys else None,
        simulated=bool(row["simulated"]) if "simulated" in keys else False,
    )


def _participant_from_row(row: sqlite3.Row) -> Participant:
    keys = row.keys()
    return Participant(
        id=row["id"],
        poll_id=row["poll_id"],
        ref=row["ref"],
        name=row["name"],
        phone_e164=row["phone_e164"],
        state=ParticipantState(row["state"]),
        call_run_id=row["call_run_id"],
        attempted_at=row["attempted_at"],
        contact_id=row["contact_id"] if "contact_id" in keys else None,
    )


def _answer_from_row(row: sqlite3.Row) -> Answer:
    try:
        structured = json.loads(row["structured_json"] or "{}")
    except (TypeError, ValueError):
        structured = {}
    keys = row.keys()
    return Answer(
        participant_id=row["participant_id"],
        call_status=CallStatus.parse(row["call_status"]),
        structured=structured if isinstance(structured, dict) else {},
        raw_text=row["raw_text"] or "",
        transcript=(row["transcript"] or "") if "transcript" in keys else "",
        received_at=row["received_at"] or "",
        run_id=row["run_id"],
        error=row["error"],
    )


def bulk_add_participants(
    store: Store, poll_id: str, people: Iterable[tuple[str, str]]
) -> list[Participant]:
    """Add ``(name, phone)`` pairs. Fails before the first insert if any is bad."""
    pairs = list(people)
    for name, phone in pairs:
        Participant(id="check", poll_id=poll_id, ref="check", name=name, phone_e164=phone)
    return [store.add_participant(poll_id, name=name, phone=phone) for name, phone in pairs]
