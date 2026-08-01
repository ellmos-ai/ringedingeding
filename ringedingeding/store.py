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

from .models import (
    Answer,
    CallStatus,
    Participant,
    ParticipantState,
    Poll,
    PollKind,
    new_id,
)

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
    status       TEXT NOT NULL DEFAULT 'open'
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
    UNIQUE (poll_id, ref)
);

CREATE TABLE IF NOT EXISTS answer (
    participant_id  TEXT PRIMARY KEY REFERENCES participant(id) ON DELETE CASCADE,
    call_status     TEXT NOT NULL,
    structured_json TEXT NOT NULL DEFAULT '{}',
    raw_text        TEXT NOT NULL DEFAULT '',
    received_at     TEXT NOT NULL,
    run_id          TEXT,
    error           TEXT
);

CREATE INDEX IF NOT EXISTS idx_participant_poll ON participant(poll_id);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PollNotFound(KeyError):
    """No poll with that id."""


class Store:
    """Thin SQLite wrapper. All writes commit immediately."""

    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        if self.path.parent and str(self.path.parent) not in ("", "."):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(_SCHEMA)
        self.connection.commit()

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
        region: str = "US",
        locale: str = "en-US",
        options: Sequence[str] = (),
        slots: Sequence[str] = (),
        poll_id: str | None = None,
    ) -> Poll:
        parsed_kind = kind if isinstance(kind, PollKind) else PollKind.parse(kind)
        if parsed_kind is PollKind.CHOICE and not options:
            raise ValueError("a 'choice' poll needs at least two options")
        if parsed_kind is PollKind.CHOICE and len(set(options)) < 2:
            raise ValueError("a 'choice' poll needs at least two distinct options")

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
        )
        self.connection.execute(
            "INSERT INTO poll (id, question, kind, organizer, language, region, locale,"
            " options_json, window_json, created_at, status)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
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

    # -- participants -------------------------------------------------------

    def add_participant(
        self,
        poll_id: str,
        *,
        name: str,
        phone: str,
        ref: str | None = None,
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
        )
        self.connection.execute(
            "INSERT INTO participant (id, poll_id, ref, name, phone_e164, state)"
            " VALUES (?,?,?,?,?,?)",
            (
                participant.id,
                participant.poll_id,
                participant.ref,
                participant.name,
                participant.phone_e164,
                participant.state.value,
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
            " received_at, run_id, error) VALUES (?,?,?,?,?,?,?)"
            " ON CONFLICT(participant_id) DO UPDATE SET"
            " call_status=excluded.call_status, structured_json=excluded.structured_json,"
            " raw_text=excluded.raw_text, received_at=excluded.received_at,"
            " run_id=excluded.run_id, error=excluded.error",
            (
                answer.participant_id,
                answer.call_status.value,
                json.dumps(answer.structured or {}, ensure_ascii=False),
                answer.raw_text or "",
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
    )


def _participant_from_row(row: sqlite3.Row) -> Participant:
    return Participant(
        id=row["id"],
        poll_id=row["poll_id"],
        ref=row["ref"],
        name=row["name"],
        phone_e164=row["phone_e164"],
        state=ParticipantState(row["state"]),
        call_run_id=row["call_run_id"],
        attempted_at=row["attempted_at"],
    )


def _answer_from_row(row: sqlite3.Row) -> Answer:
    try:
        structured = json.loads(row["structured_json"] or "{}")
    except (TypeError, ValueError):
        structured = {}
    return Answer(
        participant_id=row["participant_id"],
        call_status=CallStatus.parse(row["call_status"]),
        structured=structured if isinstance(structured, dict) else {},
        raw_text=row["raw_text"] or "",
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
